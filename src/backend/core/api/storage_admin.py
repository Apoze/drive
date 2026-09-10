"""Administrative connection endpoints; ordinary users never receive credentials."""

import posixpath
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import CharField, Q, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from rest_framework import decorators, exceptions, permissions, response, serializers, viewsets

from core.api.storage_resources import StoragePagination, reference_uuid
from core.models import (
    Item,
    StorageAdminJob,
    StorageBackend,
    StorageGrant,
    StorageQuota,
    StorageReservation,
    StorageSpace,
)
from core.services.storage_admin_jobs import enqueue_admin_job
from core.services.storage_connections import encrypt_credentials
from core.services.storage_inventory import organization_for
from core.services.storage_namespace import advisory_guard
from core.services.storage_spaces import within
from core.tasks.storage_connections import check_storage_connection


class StorageAdministrator(permissions.BasePermission):
    """Only instance administrators can configure network targets and credentials."""

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and request.user.is_active and request.user.is_superuser
        )


class StorageConnectionSerializer(serializers.ModelSerializer):
    """Public connection configuration and a write-only credential replacement."""

    credentials = serializers.DictField(
        child=serializers.CharField(trim_whitespace=False, max_length=4096),
        write_only=True,
        required=False,
    )
    credentials_configured = serializers.SerializerMethodField()
    alias_of = serializers.PrimaryKeyRelatedField(
        queryset=StorageBackend.objects.all(), write_only=True, required=False
    )

    class Meta:
        model = StorageBackend
        fields = (
            "id",
            "name",
            "organization",
            "family",
            "configuration",
            "namespace",
            "namespace_root",
            "enabled",
            "managed",
            "legacy_s3",
            "maintenance",
            "configuration_generation",
            "credentials",
            "credentials_configured",
            "alias_of",
            "connection_status",
            "connection_checked_at",
            "capacity",
            "inventory_completed_at",
            "attribution_pending",
        )
        read_only_fields = (
            "id",
            "managed",
            "legacy_s3",
            "maintenance",
            "configuration_generation",
            "connection_status",
            "connection_checked_at",
            "capacity",
            "inventory_completed_at",
            "attribution_pending",
        )

    def get_credentials_configured(self, obj):
        """Expose presence only, including externally managed credentials."""
        return bool(obj.secret_ciphertext or not obj.managed)

    @transaction.atomic
    def create(self, validated_data):
        """New connections stay disabled until a separate probe succeeds."""
        credentials = validated_data.pop("credentials", None)
        if alias := validated_data.pop("alias_of", None):
            validated_data["namespace"] = alias.namespace
        validated_data["enabled"] = False
        backend = StorageBackend(registry_id=uuid.uuid4().hex, managed=True, **validated_data)
        self._save_connection(backend, credentials)
        return backend

    @transaction.atomic
    def update(self, instance, validated_data):
        """Serialize edits and invalidate verification when configuration changes."""
        backend = StorageBackend.objects.select_for_update().get(pk=instance.pk)
        if "alias_of" in validated_data:
            raise exceptions.ValidationError("Declare aliases when creating the connection.")
        if not backend.managed and set(validated_data) - {"name", "enabled"}:
            raise exceptions.ValidationError(
                "This connection is managed by deployment configuration."
            )
        credentials = validated_data.pop("credentials", None)
        changes_configuration = credentials is not None or any(
            key in validated_data and validated_data[key] != getattr(backend, key)
            for key in ("configuration", "family")
        )
        for key, value in validated_data.items():
            setattr(backend, key, value)
        if changes_configuration:
            backend.configuration_generation += 1
            backend.connection_status = "unchecked"
            backend.enabled = False
        if backend.managed and backend.enabled and backend.connection_status != "ready":
            raise exceptions.ValidationError("Test this connection before enabling it.")
        self._save_connection(backend, credentials)
        return backend

    @staticmethod
    def _save_connection(backend, credentials):
        try:
            if credentials is not None:
                backend.secret_ciphertext = encrypt_credentials(backend, credentials)
            backend.full_clean()
            backend.save()
        except DjangoValidationError as exc:
            raise exceptions.ValidationError(exc.messages) from None


# DRF composes its standard CRUD mixins.
# pylint: disable-next=too-many-ancestors
class StorageConnectionViewSet(viewsets.ModelViewSet):
    """Connection lifecycle, with no implicit deletion of stored files."""

    permission_classes = [StorageAdministrator]
    serializer_class = StorageConnectionSerializer
    queryset = StorageBackend.objects.all().order_by("name", "id")
    pagination_class = StoragePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        if instance.enabled:
            raise exceptions.ValidationError("Disable this connection before removing it.")
        try:
            instance.delete()
        except ProtectedError:
            raise exceptions.ValidationError(
                "This connection still contains spaces, files or operations."
            ) from None

    @decorators.action(detail=True, methods=["post"], url_path="test")
    def test_connection(self, request, **_kwargs):
        """Network IO belongs to a bounded worker task, never the HTTP request."""
        backend = self.get_object()
        now = timezone.now()
        if (
            not StorageBackend.objects.filter(pk=backend.pk)
            .exclude(
                connection_status="checking", connection_checked_at__gte=now - timedelta(minutes=2)
            )
            .update(connection_status="checking", connection_checked_at=now)
        ):
            return response.Response({"state": "checking"}, status=202)
        try:
            check_storage_connection.apply_async(
                args=[str(backend.pk), backend.configuration_generation], retry=False
            )
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            StorageBackend.objects.filter(pk=backend.pk, connection_checked_at=now).update(
                connection_status="unavailable"
            )
            return response.Response({"state": "unavailable"}, status=503)
        return response.Response({"state": "checking"}, status=202)

    @decorators.action(detail=True, methods=["post"])
    def maintenance(self, request, **_kwargs):
        """Fence all views before root or ownership changes."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_tree_transfer import enter_maintenance  # noqa: PLC0415

        backend = self.get_object()
        enter_maintenance(backend)
        return response.Response({"state": "maintenance"})

    @decorators.action(detail=True, methods=["post"])
    def inventory(self, request, **_kwargs):
        """Schedule existing namespace reconciliation without doing network IO in HTTP."""
        backend = self.get_object()
        if backend.family != "mount":
            raise exceptions.ValidationError("S3 usage is maintained by file publication.")
        job = enqueue_admin_job(backend=backend, actor=request.user, kind="inventory")
        return response.Response({"state": job.state, "id": str(job.pk)}, status=202)

    @decorators.action(detail=True, methods=["post"])
    def reclassify(self, request, **_kwargs):
        """Use the existing journalled attribution task to leave maintenance."""
        backend = self.get_object()
        if not backend.maintenance:
            raise exceptions.ValidationError("Enter maintenance first.")
        job = enqueue_admin_job(backend=backend, actor=request.user, kind="reclassify")
        return response.Response({"state": job.state, "id": str(job.pk)}, status=202)


def managed_spaces(user):
    """Django staff is a trusted administrative flag, always bounded by organization."""
    spaces = StorageSpace.objects.select_related("backend", "root_item", "owner")
    if user.is_superuser:
        return spaces
    if user.is_staff:
        return spaces.filter(backend__organization=organization_for(user))
    return spaces.filter(
        Q(grants__user=user) | Q(grants__team__in=user.teams),
        grants__manageable=True,
    ).distinct()


class StorageSpaceSerializer(serializers.ModelSerializer):
    """Space administration owns roots and access, never a parallel quota policy."""

    backend_name = serializers.CharField(source="backend.name", read_only=True)
    family = serializers.CharField(source="backend.family", read_only=True)
    owner_label = serializers.SerializerMethodField()
    root_item = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.filter(
            type="folder", deleted_at__isnull=True, hard_deleted_at__isnull=True
        ),
        required=False,
        allow_null=True,
    )

    def get_owner_label(self, space):
        """Keep the configured accounting owner readable without a directory search."""
        return (space.owner.full_name or space.owner.email) if space.owner_id else ""

    usage = serializers.SerializerMethodField()

    def get_usage(self, space):
        """The UI reads the committed ledger; limits remain owned by ST."""
        account = (
            StorageQuota.objects.filter(key=f"space:{space.pk}")
            .values(
                "used_bytes",
                "reserved_bytes",
                "limit_bytes",
                "growth_blocked",
                "policy_applied_at",
                "accounting_ready_at",
            )
            .first()
        )
        return account

    class Meta:
        model = StorageSpace
        fields = (
            "id",
            "name",
            "backend",
            "root_path",
            "root_item",
            "owner",
            "owner_label",
            "enabled",
            "attribute_to_creator",
            "allow_sharing",
            "explicit_access",
            "backend_name",
            "family",
            "usage",
        )
        read_only_fields = ("id", "explicit_access")

    def validate_backend(self, backend):
        """Organization managers cannot attach another organization's connection."""
        user = self.context["request"].user
        if not user.is_superuser and (
            not user.is_staff or backend.organization != organization_for(user)
        ):
            raise exceptions.PermissionDenied()
        return backend

    def validate(self, attrs):
        backend = attrs.get("backend") or self.instance.backend
        owner = attrs.get("owner", self.instance.owner if self.instance else None)
        if owner and (not owner.is_active or organization_for(owner) != backend.organization):
            raise exceptions.ValidationError("Choose an active owner from this organization.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        space = StorageSpace(explicit_access=True, **validated_data)
        if space.backend.family == "s3":
            space.root_path = "/"
            space.root_item = space.root_item or Item.objects.create_child(
                creator=self.context["request"].user,
                type="folder",
                title=space.name,
                storage_backend=space.backend,
            )
        self._save_space(space)
        if space.root_item_id and not space.root_item.storage_space_id:
            Item.objects.filter(pk=space.root_item_id).update(storage_space=space)
        return space

    @transaction.atomic
    def update(self, instance, validated_data):
        space = StorageSpace.objects.select_for_update().get(pk=instance.pk)
        for key, value in validated_data.items():
            setattr(space, key, value)
        self._save_space(space)
        return space

    @staticmethod
    def _save_space(space):
        try:
            space.full_clean()
            space.save()
        except DjangoValidationError as exc:
            raise exceptions.ValidationError(exc.messages) from None


class StorageGrantSerializer(serializers.ModelSerializer):
    """An explicit beneficiary and a relative subtree, separate from quota ownership."""

    beneficiary = serializers.SerializerMethodField()
    root_title = serializers.CharField(source="root_item.title", read_only=True, default="")

    def get_beneficiary(self, grant):
        """Use human-readable principals in space management."""
        return (
            (grant.user.full_name or grant.user.email)
            if grant.user_id
            else self.context.get("groups", {}).get(grant.team, grant.team)
        )

    def validate_team(self, value):
        """New local-group grants must reference an existing, discoverable group."""
        if value:
            identity = value.removeprefix("group:")
            if (
                not value.startswith("group:")
                or not identity.isascii()
                or not identity.isdecimal()
                or identity != str(int(identity))
                or not self.context["available_groups"].filter(pk=identity).exists()
            ):
                raise exceptions.ValidationError("Choose an available group.")
        return value

    class Meta:
        model = StorageGrant
        fields = (
            "id",
            "user",
            "team",
            "path",
            "root_item",
            "writable",
            "shareable",
            "manageable",
            "beneficiary",
            "root_title",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        grant = StorageGrant(space=self.context["space"], **validated_data)
        try:
            grant.full_clean()
            grant.save()
        except DjangoValidationError as exc:
            raise exceptions.ValidationError(exc.messages) from None
        return grant


# pylint: disable-next=too-many-ancestors
class StorageSpaceAdminViewSet(viewsets.ModelViewSet):
    """Organization and delegated managers operate only their authorized spaces."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StorageSpaceSerializer
    pagination_class = StoragePagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if not self.request.user.is_active:
            return StorageSpace.objects.none()
        return managed_spaces(self.request.user).order_by("name", "id")

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_active or not (user.is_superuser or user.is_staff):
            raise exceptions.PermissionDenied()
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if not (user.is_superuser or user.is_staff) and set(serializer.validated_data) - {"name"}:
            raise exceptions.PermissionDenied(
                "Only organization administrators change space policy."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            raise exceptions.PermissionDenied()
        if instance.enabled or instance.items.exists():
            raise exceptions.ValidationError("Disable and empty this space before removing it.")
        try:
            instance.delete()
        except ProtectedError:
            raise exceptions.ValidationError(
                "Accounting or operations still reference this space."
            ) from None

    @decorators.action(detail=True, methods=["get", "post", "delete"])
    def grants(self, request, **_kwargs):
        """Replace permissions explicitly, with immediate revocation on all IO paths."""
        space = self.get_object()
        if request.method == "GET":
            rows = space.grants.select_related("user", "root_item").order_by("id")
            page = self.paginate_queryset(rows)
            group_ids = [grant.team[6:] for grant in page if grant.team.startswith("group:")]
            names = {
                f"group:{group.pk}": group.name
                for group in Group.objects.filter(pk__in=[pk for pk in group_ids if pk.isdecimal()])
            }
            return self.get_paginated_response(
                StorageGrantSerializer(page, many=True, context={"groups": names}).data
            )
        if request.method == "DELETE":
            grant = space.grants.filter(pk=reference_uuid(request.data.get("id"))).first()
            if not grant:
                raise exceptions.NotFound()
            grant.delete()
            return response.Response(status=204)
        serializer = StorageGrantSerializer(
            data=request.data, context={"space": space, "available_groups": self._groups(space)}
        )
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("manageable") and not (
            request.user.is_superuser or request.user.is_staff
        ):
            raise exceptions.PermissionDenied("Only administrators delegate space management.")
        serializer.save()
        return response.Response(serializer.data, status=201)

    def _groups(self, space):
        groups = Group.objects.all()
        if not self.request.user.is_superuser:
            groups = (
                groups.alias(storage_team=Concat(Value("group:"), Cast("pk", CharField())))
                .filter(Q(user=self.request.user) | Q(storage_team__in=space.grants.values("team")))
                .distinct()
            )
        return groups

    @decorators.action(detail=True, methods=["get"])
    def groups(self, request, **_kwargs):
        """Search group names without exposing their members or Django permissions."""
        space = self.get_object()
        query = str(request.query_params.get("q", ""))[:150]
        page = self.paginate_queryset(
            self._groups(space).filter(name__icontains=query).order_by("name", "pk")
        )
        return self.get_paginated_response(
            [{"id": f"group:{group.pk}", "name": group.name} for group in page]
        )

    @decorators.action(detail=False, methods=["get"])
    def configuration(self, request):
        """Expose role-appropriate choices, without technical configuration to delegates."""
        user = request.user
        if not user.is_active:
            raise exceptions.PermissionDenied()
        administrator = user.is_superuser or user.is_staff
        connections = (
            StorageBackend.objects.all()
            if user.is_superuser
            else StorageBackend.objects.filter(organization=organization_for(user))
        )
        return response.Response(
            {
                "connections_manage": user.is_superuser,
                "spaces_create": administrator,
                "spaces_manage": administrator or managed_spaces(user).exists(),
                "organization": organization_for(user),
                "connections": list(
                    connections.order_by("name", "id").values("id", "name", "family")[:200]
                )
                if administrator
                else [],
                "quota_url": settings.STORAGE_ADMIN_URL,
                "certificate_authorities": list(settings.STORAGE_CA_BUNDLES)
                if user.is_superuser
                else [],
            }
        )

    @decorators.action(detail=True, methods=["get"], url_path="quota-link")
    def quota_link(self, request, **_kwargs):
        """Open the exact ST organization and resource; ST still enforces its own roles."""
        # pylint: disable-next=import-outside-toplevel
        from urllib.parse import urlencode, urlsplit, urlunsplit  # noqa: PLC0415

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.entitlements import get_entitlements_backend  # noqa: PLC0415

        space = self.get_object()
        if not (request.user.is_staff or request.user.is_superuser):
            raise exceptions.PermissionDenied()
        backend = get_entitlements_backend()
        reader = getattr(backend, "get_organization_storage_policy", None)
        base = urlsplit(settings.STORAGE_ADMIN_URL)
        if not callable(reader) or base.scheme not in {"http", "https"} or not base.netloc:
            raise exceptions.ValidationError("Storage policy administration is not configured.")
        context = reader(space.backend.organization).get("administration", {})
        if not context.get("organization") or not context.get("operator"):
            raise exceptions.ValidationError(
                "This organization has no storage administration context."
            )
        organization_id = reference_uuid(context["organization"])
        operator_id = reference_uuid(context["operator"])
        return response.Response(
            {
                "url": urlunsplit(
                    (
                        base.scheme,
                        base.netloc,
                        f"{base.path.rstrip('/')}/operators/{operator_id}"
                        f"/organizations/{organization_id}",
                        urlencode(
                            {
                                "service_id": backend.service_id,
                                "resource_type": "storage_space",
                                "resource_id": str(space.pk),
                            }
                        ),
                        "",
                    )
                )
            }
        )

    @staticmethod
    def _overlaps(space, siblings):
        if space.backend.family == "s3":
            if not space.root_item_id:
                return []
            siblings = siblings.filter(
                Q(root_item__path__ancestors=space.root_item.path)
                | Q(root_item__path__descendants=space.root_item.path)
            )
        else:
            siblings = (
                other
                for other in siblings
                if within(space.root_path, other.root_path)
                or within(other.root_path, space.root_path)
            )
        return [{"id": str(other.pk), "name": other.name} for other in siblings]

    @decorators.action(detail=False, methods=["get"], url_path="root-folders")
    def root_folders(self, request):
        """Browse existing S3 roots for an administrator before allocating a subtree."""
        user = request.user
        if not user.is_active or not (user.is_superuser or user.is_staff):
            raise exceptions.PermissionDenied()
        connections = StorageBackend.objects.filter(family="s3")
        if not user.is_superuser:
            connections = connections.filter(organization=organization_for(user))
        backend = connections.filter(pk=reference_uuid(request.query_params.get("backend"))).first()
        if not backend:
            raise exceptions.NotFound()
        folders = Item.objects.filter(
            storage_backend=backend,
            type="folder",
            deleted_at__isnull=True,
            hard_deleted_at__isnull=True,
        )
        parent = None
        if identity := request.query_params.get("parent"):
            parent = folders.filter(pk=reference_uuid(identity)).first()
            if not parent:
                raise exceptions.NotFound()
            folders = folders.filter(path__in=parent.children().values("path"))
        else:
            folders = folders.filter(path__depth=1)
        result = self.get_paginated_response(
            list(self.paginate_queryset(folders.order_by("title", "pk").values("id", "title")))
        )
        siblings = managed_spaces(user).filter(backend=backend)
        result.data["allocated"] = bool(parent and siblings.filter(root_item=parent).exists())
        result.data["overlaps"] = self._overlaps(
            StorageSpace(backend=backend, root_item=parent), siblings
        )
        return result

    @decorators.action(detail=True, methods=["get"])
    def folders(self, request, **_kwargs):
        """Choose a grant root by logical identity, without exposing any file contents."""
        space = self.get_object()
        if space.backend.family != "s3":
            raise exceptions.NotFound()
        root = space.root_item
        if parent := request.query_params.get("parent"):
            root = Item.objects.filter(
                pk=reference_uuid(parent),
                storage_backend=space.backend,
                path__descendants=space.root_item.path,
                type="folder",
                deleted_at__isnull=True,
                hard_deleted_at__isnull=True,
            ).first()
        if not root:
            raise exceptions.NotFound()
        rows = (
            root.children()
            .filter(type="folder", deleted_at__isnull=True, hard_deleted_at__isnull=True)
            .order_by("title", "id")
            .values("id", "title")
        )
        return self.get_paginated_response(list(self.paginate_queryset(rows)))

    @decorators.action(
        detail=True,
        methods=["post"],
        permission_classes=[StorageAdministrator],
        url_path="initialize-root",
    )
    def initialize_root(self, request, **_kwargs):
        """Create a missing configured NAS root with the connection's technical rights."""
        space = self.get_object()
        if space.backend.family != "mount" or not space.backend.enabled:
            raise exceptions.ValidationError("Choose an enabled filesystem connection.")
        job = enqueue_admin_job(backend=space.backend, actor=request.user, kind="root", space=space)
        return response.Response({"state": job.state, "id": str(job.pk)}, status=202)

    @decorators.action(detail=True, methods=["get"])
    def impact(self, request, **_kwargs):
        """Preview overlaps and live operations before changing a space."""
        space = self.get_object()
        siblings = (
            managed_spaces(request.user)
            .filter(backend__namespace=space.backend.namespace)
            .exclude(pk=space.pk)
        )
        overlaps = self._overlaps(space, siblings)
        return response.Response(
            {
                "overlaps": overlaps,
                "active_operations": StorageReservation.objects.filter(
                    resource_key__in=space.storageusage_set.values("key"),
                    state__in=["reserved", "writing", "publishing"],
                ).count(),
                "quota_url": settings.STORAGE_ADMIN_URL,
                "quota_resource": {"type": "storage_space", "id": str(space.pk)},
            }
        )


# Input validation only; the job service owns publication and recovery.
# pylint: disable-next=abstract-method
class StorageRestoreSerializer(serializers.Serializer):
    """A retained version and a virtual destination never accept native credentials."""

    version = serializers.UUIDField()
    space = serializers.UUIDField()
    path = serializers.CharField(max_length=2048)


class StorageAdminJobViewSet(viewsets.GenericViewSet):
    """Inspect durable administrative work without exposing native paths or secrets."""

    permission_classes = [StorageAdministrator]
    pagination_class = StoragePagination
    queryset = StorageAdminJob.objects.select_related("backend", "space").order_by("-created_at")

    @staticmethod
    def _serialize(job):
        return {
            "id": str(job.pk),
            "kind": job.kind,
            "state": job.state,
            "connection": job.backend.name,
            "space": job.space.name if job.space_id else "",
            "reason": job.reason,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "can_retry": job.state == "failed",
            "can_cancel": job.state == "queued" and not job.operation_id,
        }

    def list(self, request):
        """Bound history before serialization; only instance administrators can read it."""
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([self._serialize(job) for job in page])

    def retrieve(self, request, **_kwargs):
        """Observe the recorded state after a request timeout or worker restart."""
        return response.Response(self._serialize(self.get_object()))

    @staticmethod
    def _retained():
        return StorageReservation.objects.filter(
            Q(
                publication__native_source__backup_path__isnull=False,
                publication__source_retained=True,
            )
            | (
                (Q(publication__kind="mount") | Q(publication__source_kind="file"))
                & Q(publication__cleanup_pending=True, publication__backup_path__isnull=False)
                & ~Q(publication__backup_path=None)
            ),
            state="committed",
        )

    @decorators.action(detail=False, methods=["get"], url_path="retained-versions")
    def retained_versions(self, request):
        """List retained file metadata; the worker confirms native availability."""
        page = self.paginate_queryset(self._retained().order_by("-updated_at"))
        return self.get_paginated_response(
            [
                {
                    "id": str(operation.pk),
                    "title": posixpath.basename(
                        (operation.publication.get("native_source") or operation.publication)[
                            "path"
                        ]
                    ),
                    "bytes": operation.previous_size,
                    "retained_at": operation.updated_at,
                }
                for operation in page
            ]
        )

    @decorators.action(detail=False, methods=["post"], serializer_class=StorageRestoreSerializer)
    def restore(self, request):
        """Queue a new file; restoration never overwrites an existing destination."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.mounts.paths import (  # noqa: PLC0415
            MountPathNormalizationError,
            normalize_mount_path,
        )

        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.services.storage_spaces import authorize, resolve_space_mount  # noqa: PLC0415

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        source = self._retained().filter(pk=data["version"]).first()
        space = StorageSpace.objects.select_related("backend").filter(pk=data["space"]).first()
        try:
            destination = normalize_mount_path(data["path"])
        except MountPathNormalizationError:
            raise exceptions.ValidationError(
                "Choose a valid path inside the destination space."
            ) from None
        if (
            not source
            or not space
            or not resolve_space_mount(space.pk, request.user)
            or destination == "/"
        ):
            raise exceptions.NotFound()
        authorize(space, request.user, destination, write=True)
        job = enqueue_admin_job(
            backend=space.backend,
            actor=request.user,
            kind="restore",
            space=space,
            source_operation=source,
            destination=destination,
        )
        return response.Response(self._serialize(job), status=202)

    @decorators.action(detail=True, methods=["post"])
    def retry(self, request, **_kwargs):
        """Keep failed attempts in history and enqueue a new snapshot after review."""
        job = self.get_object()
        with advisory_guard(f"storage-admin:{job.pk}"):
            job.refresh_from_db()
            if job.state != "failed":
                raise exceptions.ValidationError(
                    "This operation is still active or already complete."
                )
            if job.space_id and job.space.root_path != job.payload["root_path"]:
                raise exceptions.ValidationError(
                    "The root changed. Start the operation from its current space."
                )
            if job.operation_id and job.operation.state != "cancelled":
                # The recorded publication resumes with its existing quota reservations.
                # pylint: disable-next=import-outside-toplevel,cyclic-import
                from core.services.storage_admin_jobs import dispatch_admin_job  # noqa: PLC0415

                job.state, job.reason = "queued", ""
                job.actor = request.user
                job.payload = {**job.payload, "recovered_by": str(request.user.pk)}
                job.save(update_fields=["state", "reason", "actor", "payload", "updated_at"])
                dispatch_admin_job(job.pk)
                return response.Response(self._serialize(job), status=202)
            following = enqueue_admin_job(
                backend=job.backend,
                actor=request.user,
                kind=job.kind,
                space=job.space,
                source_operation=job.source_operation,
                destination=job.payload.get("destination"),
            )
            return response.Response(self._serialize(following), status=202)

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request, **_kwargs):
        """Cancel only work that has not started; published changes cannot be undone here."""
        job = self.get_object()
        with advisory_guard(f"storage-admin:{job.pk}"):
            job.refresh_from_db()
            if job.state != "queued" or job.operation_id:
                raise exceptions.ValidationError("This operation has already started.")
            job.state, job.reason = "failed", "Cancelled before execution."
            job.save(update_fields=["state", "reason", "updated_at"])
        return response.Response(self._serialize(job))
