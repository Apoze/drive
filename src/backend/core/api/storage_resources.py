"""One catalogue and stable resource navigation for Items and mounted entries."""

from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.db.models import Case, Exists, F, Max, OuterRef, Q, UUIDField, Value, When
from django.utils import timezone

from rest_framework import decorators, exceptions, permissions, response, viewsets
from rest_framework.pagination import LimitOffsetPagination

from core.models import (
    DocsBinding,
    Item,
    LinkTrace,
    MountShareLink,
    StorageQuota,
    StorageResource,
    StorageResourceFavorite,
)
from core.mounts.paths import MountPathNormalizationError, normalize_mount_path
from core.mounts.providers.base import MountEntry, MountProviderError
from core.mounts.registry import get_mount_provider
from core.services.storage_access import bound_queryset, cache_item_grants
from core.services.storage_resources import (
    create_resource_share,
    item_entrances,
    mounted_queryset,
    observe_virtual_entry,
    resolve_mounted,
    resolve_resource_space,
    space_entrances,
    space_root,
    visible_spaces,
)
from core.services.storage_spaces import authorize, resolve_space_mount, within


def reference_uuid(value):
    """Malformed external identifiers never reach a model UUID lookup."""
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise exceptions.NotFound() from None


class StoragePagination(LimitOffsetPagination):
    """Keep metadata requests bounded, including administrator-created large spaces."""

    default_limit = 50
    max_limit = 200


def serialize_item(item, request, *, payload=None):
    """Retain established viewer and file-action payloads behind the resource contract."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.api.serializers import ItemSerializer  # noqa: PLC0415

    if payload is None:
        payload = ItemSerializer(item, context={"request": request}).data
    space_id = item.storage_space_id
    if item.type == "docs":
        from core.services.docs_resources import placement  # noqa: PLC0415

        _, space = placement(item)
        space_id = space.pk if space else None
    return {
        "id": str(item.pk),
        "space": str(space_id) if space_id else "",
        "title": item.title,
        "kind": item.type,
        "size": item.size,
        "updated_at": item.updated_at,
        "abilities": payload["abilities"],
        "adapter": {
            "kind": "item",
            "item": payload,
        },
    }


def serialize_items(items, request):
    """Reuse the existing explorer's page annotations and ancestor-link grouping."""
    # pylint: disable=import-outside-toplevel,cyclic-import,protected-access
    from core.api.serializers import ItemSerializer  # noqa: PLC0415
    from core.api.viewsets import ItemViewSet  # noqa: PLC0415
    from core.services.docs_resources import document_page  # noqa: PLC0415

    items = list(items)
    with document_page(items, request.user):
        cache_item_grants(items, request.user)
        # pylint: disable-next=protected-access
        mapping = ItemViewSet()._compute_ancestors_link_definition(items)  # noqa: SLF001
        context = {
            "request": request,
            "paths_links_mapping": mapping,
        }
        payloads = ItemSerializer(items, many=True, context=context).data
        return [
            serialize_item(item, request, payload=payload)
            for item, payload in zip(items, payloads, strict=True)
        ]


def item_metadata(queryset, user):
    """Prepare the same complete item metadata for every common catalogue page."""
    return (
        queryset.select_related("creator", "storage_backend", "storage_space__backend")
        .annotate_is_favorite(user)
        .annotate_user_roles(user)
        .annotate_with_numchild()
    )


def serialize_mounted(resource, space, request):
    """Adapters expose virtual paths only; native roots and connection secrets stay private."""
    # pylint: disable-next=import-outside-toplevel,cyclic-import
    from core.api.viewsets import MountViewSet  # noqa: PLC0415

    path = resource.path[len(space_root(space).rstrip("/")) :] or "/"
    mounts = request.__dict__.setdefault("_storage_mounts", {})
    mount = mounts.get(space.pk)
    if mount is None:
        mount = resolve_space_mount(space.pk, request.user)
        if mount:
            mount["_browse_context"] = (space, request.user)
            mounts[space.pk] = mount
    if not mount:
        raise exceptions.NotFound()
    entry = MountEntry(
        resource.kind,
        path,
        resource.name,
        resource.size,
        resource.modified_at,
        resource.provider_identity,
    )
    view = MountViewSet()
    view.request = request
    payload = view.mount_entry_payload(
        mount_id=str(space.pk),
        mount=mount,
        provider=get_mount_provider("virtual"),
        entry=entry,
        capabilities=view.mount_capabilities(mount),
    )
    return {
        "id": str(resource.pk),
        "space": str(space.pk),
        "title": space.name if path == "/" else resource.name,
        "kind": resource.kind,
        "size": resource.size,
        "updated_at": resource.modified_at,
        "abilities": payload["abilities"],
        "observed_at": resource.updated_at,
        "adapter": {
            "kind": "mount",
            "mount_id": str(space.pk),
            "path": path,
            "entry": payload,
            "capabilities": view.mount_capabilities(mount),
        },
    }


def serialize_resource_page(page, request, spaces):
    """Load only one mixed SQL page and retain its common ordering."""
    native_items = item_metadata(Item.objects.all(), request.user).in_bulk(
        row["reference"] for row in page if row["family"] == "item"
    )
    native_payloads = {row["id"]: row for row in serialize_items(native_items.values(), request)}
    mounted = StorageResource.objects.in_bulk(
        row["reference"] for row in page if row["family"] == "mount"
    )
    return [
        native_payloads[str(row["reference"])]
        if row["family"] == "item"
        else serialize_mounted(mounted[row["reference"]], spaces[row["space_reference"]], request)
        for row in page
    ]


def items_in_space(items, space, user):
    """Constrain both binary items and document trees before mixed pagination."""
    if space is None:
        return items.none()
    if space.backend.family == "mount":
        if not getattr(settings, "DOCS_DRIVE_ENABLED", False):
            return items.none()
        anchors = DocsBinding.objects.filter(
            anchor_space=space,
            mounted_parent__in=mounted_queryset(space, user),
            item__path__ancestors=OuterRef("path"),
        )
        return items.alias(_in_requested_mount=Exists(anchors)).filter(
            type="docs", _in_requested_mount=True
        )
    if space.root_item_id:
        return items.filter(
            Q(storage_backend=space.backend) | Q(type="docs"),
            path__descendants=space.root_item.path,
        )
    return items.none()


def collection_ordering(request, mode):
    """Use the historical explorer column ordering across one mixed SQL page."""
    ordering = ["-seen", "reference", "space_reference"]
    if mode == "home":
        fields = {
            "title": "label",
            "type": "entry_kind",
            "size": "entry_size",
            "created_at": "entry_created",
            "updated_at": "seen",
            "creator__full_name": "entry_creator",
        }
        ordering = []
        for field in request.query_params.get("ordering", "-type,title").split(","):
            if field.lstrip("-") not in fields:
                raise exceptions.ValidationError("Invalid resource ordering.")
            ordering.append(("-" if field.startswith("-") else "") + fields[field.lstrip("-")])
        ordering.extend(["reference", "space_reference"])
    return ordering


def filter_home_mounts(mounted, filters, spaces):
    """Apply the same validated date/contact filters to allocated native roots."""
    if filters.data.get("type") not in {None, "folder"}:
        mounted = mounted.none()
    date_filter = filters.filters["updated_at"]
    mounted = date_filter.filter(mounted, filters.form.cleaned_data["updated_at"])
    if contact := filters.form.cleaned_data.get("contact"):
        from core.models import User  # noqa: PLC0415

        person = User.objects.filter(pk=contact).first()
        shared = Q(pk__in=[])
        if person:
            for space in spaces.values():
                shared |= Q(pk__in=mounted_queryset(space, person).values("pk"))
        mounted = mounted.filter(shared)
    return mounted


class SpaceViewSet(viewsets.ReadOnlyModelViewSet):
    """Discover permitted entrances, including restricted subfolders of shared spaces."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StoragePagination

    def get_queryset(self):
        # Historical single-file allocations remain in My files; they are not
        # folders that users can choose as a storage destination.
        return visible_spaces(self.request.user).exclude(root_item__type="file")

    def _serialize(self, space):
        user = self.request.user
        roots = []
        if space.backend.family == "s3":
            roots = [
                {
                    "id": str(item.pk),
                    "title": item.title,
                    "updated_at": item.updated_at,
                    "abilities": item.get_abilities(user),
                }
                for item in space_entrances(space, user)
            ]
        else:
            root = space_entrances(space, user).first()
            if root:
                roots = [
                    {
                        "id": str(root.pk),
                        "title": space.name,
                        "updated_at": root.modified_at or root.updated_at,
                        "abilities": serialize_mounted(root, space, self.request)["abilities"],
                    }
                ]
        budget = StorageQuota.objects.filter(key=f"space:{space.pk}").first()
        return {
            "id": str(space.pk),
            "name": space.name,
            "updated_at": space.updated_at,
            "roots": roots,
            "state": "maintenance"
            if space.backend.maintenance
            else "ready"
            if roots
            else "index_pending",
            "inventory_updated_at": space.backend.inventory_completed_at,
            "usage": {
                "used": budget.used_bytes if budget else 0,
                "reserved": budget.reserved_bytes if budget else 0,
                "limit": budget.limit_bytes if budget else None,
                "growth_blocked": budget.growth_blocked if budget else False,
                "policy_applied_at": budget.policy_applied_at if budget else None,
            },
        }

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([self._serialize(space) for space in page])

    def retrieve(self, request, *args, **kwargs):
        return response.Response(self._serialize(self.get_object()))


class ResourceViewSet(viewsets.ViewSet):
    """Resolve current permissions for every reference, including favorites and old links."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StoragePagination

    def list(self, request):
        """Search/favorites/recent share permission-filtered metadata and bounded pagination."""
        # pylint: disable-next=import-outside-toplevel,cyclic-import
        from core.api.viewsets import ItemViewSet  # noqa: PLC0415

        query = str(request.query_params.get("q", "")).strip()[:200]
        mode = request.query_params.get("mode", "search")
        if mode not in {"search", "favorites", "recent", "home"}:
            raise exceptions.ValidationError("Invalid resource collection.")
        items_view = ItemViewSet()
        items_view.request, items_view.detail, items_view.action = request, False, "search"
        items = bound_queryset(items_view.get_queryset_for_descendants(), request.user)
        if mode == "home":
            items = items.filter(pk__in=item_entrances(request.user).values("pk"))
            from core.api.filters import ItemFilter  # noqa: PLC0415

            filters = ItemFilter(request.query_params, queryset=items, request=request)
            if not filters.is_valid():
                raise exceptions.ValidationError(filters.errors)
            items = filters.qs
        if requested := request.query_params.get("space"):
            try:
                requested = UUID(requested)
            except ValueError:
                raise exceptions.ValidationError("Invalid space reference.") from None
            selected_space = visible_spaces(request.user).filter(pk=requested).first()
            items = items_in_space(items, selected_space, request.user)
        if mode == "favorites":
            items = items.favorited_by(request.user)
        if mode == "recent":
            items = items.filter(link_traces__user=request.user)
        items = (
            items.filter(title__icontains=query)
            .order_by()
            .annotate(
                reference=F("pk"),
                space_reference=F("storage_space_id"),
                label=F("title"),
                family=Value("item"),
                seen=Max("link_traces__updated_at") if mode == "recent" else F("updated_at"),
                entry_kind=F("type"),
                entry_size=F("size"),
                entry_created=F("created_at"),
                entry_creator=F("creator__full_name"),
            )
            .values(
                "reference",
                "space_reference",
                "label",
                "family",
                "seen",
                "entry_kind",
                "entry_size",
                "entry_created",
                "entry_creator",
            )
        )
        spaces = visible_spaces(request.user)
        if requested:
            spaces = spaces.filter(pk=requested)
        spaces = {space.pk: space for space in spaces.filter(backend__family="mount")}
        collections = []
        if spaces:
            # Select a current authorized view before pagination; overlapping
            # spaces must not duplicate the same logical search/favorite result.
            mounted = (
                StorageResource.objects.filter(name__icontains=query)
                .annotate(
                    space_reference=Case(
                        *[
                            When(
                                pk__in=(
                                    space_entrances(space, request.user)
                                    if mode == "home"
                                    else mounted_queryset(space, request.user)
                                ).values("pk"),
                                then=Value(space.pk),
                            )
                            for space in spaces.values()
                        ],
                        output_field=UUIDField(),
                    )
                )
                .filter(space_reference__isnull=False)
            )
            if mode == "home":
                mounted = filter_home_mounts(mounted, filters, spaces)
            if mode == "favorites":
                mounted = mounted.filter(
                    storageresourcefavorite__user=request.user,
                    storageresourcefavorite__favorite=True,
                )
            if mode == "recent":
                mounted = mounted.filter(
                    storageresourcefavorite__user=request.user,
                    storageresourcefavorite__last_opened_at__isnull=False,
                )
            collections.append(
                mounted.order_by()
                .annotate(
                    reference=F("pk"),
                    label=(
                        Case(
                            *[
                                When(space_reference=space.pk, then=Value(space.name))
                                for space in spaces.values()
                            ],
                            default=F("name"),
                        )
                        if mode == "home"
                        else F("name")
                    ),
                    family=Value("mount"),
                    seen=F("storageresourcefavorite__last_opened_at")
                    if mode == "recent"
                    else F("updated_at"),
                    entry_kind=F("kind"),
                    entry_size=F("size"),
                    entry_created=F("created_at"),
                    entry_creator=Value(""),
                )
                .values(
                    "reference",
                    "space_reference",
                    "label",
                    "family",
                    "seen",
                    "entry_kind",
                    "entry_size",
                    "entry_created",
                    "entry_creator",
                )
            )
        ordering = collection_ordering(request, mode)
        rows = (items.union(*collections) if collections else items).order_by(*ordering)
        pagination = StoragePagination()
        page = pagination.paginate_queryset(rows, request)
        return pagination.get_paginated_response(serialize_resource_page(page, request, spaces))

    def _target(self, request, pk):
        pk = reference_uuid(pk)
        item = (
            bound_queryset(item_metadata(Item.objects.all(), request.user), request.user)
            .filter(pk=pk, hard_deleted_at__isnull=True)
            .first()
        )
        if item:
            if not item.get_abilities(request.user).get("retrieve"):
                raise exceptions.NotFound()
            return item, item.storage_space
        preferred = request.query_params.get("space")
        return resolve_resource_space(
            pk, request.user, reference_uuid(preferred) if preferred else None
        )

    def retrieve(self, request, pk=None):
        """Open an authorized resource and record its recent-use reference."""
        resource, space = self._target(request, pk)
        if isinstance(resource, Item):
            LinkTrace.objects.update_or_create(
                user=request.user, item=resource, defaults={"updated_at": timezone.now()}
            )
            return response.Response(serialize_item(resource, request))
        StorageResourceFavorite.objects.update_or_create(
            user=request.user,
            resource=resource,
            defaults={"last_opened_at": timezone.now(), "space": space},
        )
        return response.Response(serialize_mounted(resource, space, request))

    @decorators.action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """Queue a converted sibling with the existing durable copy journal."""
        # pylint: disable=import-outside-toplevel,cyclic-import
        from pathlib import PurePosixPath  # noqa: PLC0415

        from core.services.storage_copy_job import enqueue_copy  # noqa: PLC0415
        from core.services.storage_transfer_location import resolve_location  # noqa: PLC0415
        from wopi.conversion.native import native_conversion_target  # noqa: PLC0415

        source = resolve_location(
            reference_uuid(pk), request.user, space_id=request.query_params.get("space")
        )
        if source.backend.family != "mount" or source.kind != "file":
            raise exceptions.ValidationError("Select a native file to convert.")
        resolve_mounted(source.reference.pk, source.space, request.user, write=True)
        extension = native_conversion_target(source.name)
        if not extension:
            raise exceptions.ValidationError("Conversion is not configured for this file.")
        parent = (
            mounted_queryset(source.space, request.user)
            .filter(path=source.reference.parent_path, kind="folder")
            .first()
        )
        if parent is None:
            raise exceptions.NotFound()
        destination = resolve_location(
            parent.pk, request.user, space_id=source.space.pk, destination=True
        )
        job = enqueue_copy(
            actor=request.user,
            source=source,
            destination=destination,
            name=f"{PurePosixPath(source.name).stem} (converted).{extension}",
            conversion=extension,
        )
        return response.Response({"id": str(job.pk), "state": job.state}, status=202)

    @decorators.action(detail=True, methods=["post"], url_path="new-file")
    def new_file(self, request, pk=None):
        """Create native documents with the same filename/templates and governed writer."""
        # pylint: disable=import-outside-toplevel,cyclic-import
        from core.api.serializers import CreateNewFileSerializer  # noqa: PLC0415
        from core.services.file_creation import create_native_file  # noqa: PLC0415
        from core.services.storage_transfer_location import resolve_location  # noqa: PLC0415

        target = resolve_location(
            reference_uuid(pk),
            request.user,
            space_id=request.query_params.get("space"),
            destination=True,
        )
        if target.backend.family != "mount":
            raise exceptions.ValidationError("Use the regular document creation endpoint.")
        serializer = CreateNewFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resource = create_native_file(target, serializer.validated_data)
        except MountProviderError as exc:
            raise exceptions.ValidationError({"detail": exc.public_message}) from None
        return response.Response(serialize_mounted(resource, target.space, request), status=201)

    @decorators.action(detail=True, methods=["get"])
    def children(self, request, pk=None):
        """List a permitted folder using bounded metadata pagination."""
        resource, space = self._target(request, pk)
        pagination = StoragePagination()
        if isinstance(resource, Item):
            if resource.type not in {"folder", "docs"}:
                raise exceptions.ValidationError("This resource is not a folder.")
            children = item_metadata(
                bound_queryset(resource.children(), request.user)
                .filter(
                    deleted_at__isnull=True,
                )
                .exclude(upload_state__in=["pending", "suspicious"]),
                request.user,
            )
            if request.query_params.get("kind") == "folder":
                children = children.filter(type="folder")
            page = pagination.paginate_queryset(children.order_by("title", "id"), request)
            return pagination.get_paginated_response(serialize_items(page, request))
        if resource.kind != "folder":
            raise exceptions.ValidationError("This resource is not a folder.")
        children = (
            mounted_queryset(space, request.user, traverse=True)
            .filter(parent_path=resource.path)
            .exclude(pk=resource.pk)
        )
        if request.query_params.get("kind") == "folder":
            children = children.filter(kind="folder")
        if settings.DOCS_DRIVE_ENABLED and request.query_params.get("kind") != "folder":
            documents = bound_queryset(
                Item.objects.filter(
                    type="docs",
                    docs_binding__mounted_parent=resource,
                    docs_binding__anchor_space=space,
                    ancestors_deleted_at__isnull=True,
                ),
                request.user,
            )
            columns = ("reference", "space_reference", "label", "family", "seen")
            files = (
                children.order_by()
                .annotate(
                    reference=F("pk"),
                    space_reference=Value(space.pk, output_field=UUIDField()),
                    label=F("name"),
                    family=Value("mount"),
                    seen=F("updated_at"),
                )
                .values(*columns)
            )
            documents = (
                documents.order_by()
                .annotate(
                    reference=F("pk"),
                    space_reference=Value(space.pk, output_field=UUIDField()),
                    label=F("title"),
                    family=Value("item"),
                    seen=F("updated_at"),
                )
                .values(*columns)
            )
            page = pagination.paginate_queryset(
                files.union(documents).order_by("label", "reference"), request
            )
            return pagination.get_paginated_response(
                serialize_resource_page(page, request, {space.pk: space})
            )
        page = pagination.paginate_queryset(children.order_by("name", "id"), request)
        return pagination.get_paginated_response(
            [serialize_mounted(row, space, request) for row in page]
        )

    @decorators.action(detail=True, methods=["post", "delete"])
    def favorite(self, request, pk=None):
        """Keep per-user favorites attached to the stable resource reference."""
        resource, space = self._target(request, pk)
        if isinstance(resource, Item):
            # pylint: disable-next=import-outside-toplevel,cyclic-import
            from core.models import ItemFavorite  # noqa: PLC0415

            if request.method == "POST":
                ItemFavorite.objects.get_or_create(user=request.user, item=resource)
            else:
                ItemFavorite.objects.filter(user=request.user, item=resource).delete()
        else:
            StorageResourceFavorite.objects.update_or_create(
                user=request.user,
                resource=resource,
                defaults={"favorite": request.method == "POST", "space": space},
            )
        return response.Response(status=204)

    @decorators.action(detail=True, methods=["get", "post", "delete"], url_path="public-links")
    def public_links(self, request, pk=None):
        """Manage persistent public links across moves; ownership never bypasses file grants."""
        resource, space = self._target(request, pk)
        path = None
        if isinstance(resource, Item):
            manageable = bool(resource.get_abilities(request.user).get("link_configuration"))
        else:
            try:
                _, path = resolve_mounted(resource.pk, space, request.user, share=True)
                manageable = True
            except exceptions.NotFound:
                manageable = False
        links = MountShareLink.objects.filter(resource_id=resource.pk).order_by("created_at", "pk")
        if not manageable:
            links = links.filter(created_by=request.user)
        if request.method == "DELETE":
            link_id = reference_uuid(request.data.get("link"))
            if not links.filter(pk=link_id).delete()[0]:
                raise exceptions.NotFound()
            return response.Response(status=204)
        if request.method == "POST":
            if not manageable or isinstance(resource, Item):
                raise exceptions.PermissionDenied()
            create_resource_share(resource, request.user, mount_id=space.pk, path=path)
        pagination = StoragePagination()
        page = pagination.paginate_queryset(links, request)
        return pagination.get_paginated_response(
            [
                {
                    "id": str(link.pk),
                    "created_at": link.created_at,
                    "url": settings.DRIVE_PUBLIC_URL.rstrip("/") + f"/share/mount/{link.token}",
                }
                for link in page
            ]
        )

    @decorators.action(detail=False, methods=["get"], url_path="resolve-legacy")
    def resolve_legacy(self, request):
        """Old mount bookmarks are resolved only within an authorized virtual space."""
        try:
            path = normalize_mount_path(request.query_params.get("path", "/"))
        except MountPathNormalizationError:
            raise exceptions.ValidationError("Invalid storage path.") from None
        mount_id = request.query_params.get("mount_id", "")
        spaces = visible_spaces(request.user).filter(backend__family="mount")
        try:
            space = spaces.filter(pk=UUID(mount_id)).first()
        except (ValueError, TypeError):
            space = None
        if space is None:
            # Registry bookmarks contain a native path. Resolve only an authorized
            # view that contains it, then let the normal grant filter decide access.
            candidates = [
                candidate
                for candidate in spaces.filter(backend__registry_id=mount_id)
                if within(path, candidate.root_path)
            ]
            candidates.sort(key=lambda candidate: (-len(candidate.root_path), str(candidate.pk)))
            for candidate in candidates:
                try:
                    authorize(
                        candidate,
                        request.user,
                        path[len(candidate.root_path.rstrip("/")) :] or "/",
                        traverse=True,
                    )
                except MountProviderError:
                    continue
                space = candidate
                break
            if space:
                path = path[len(space.root_path.rstrip("/")) :] or "/"
        if not space:
            raise exceptions.NotFound()
        canonical = space_root(space).rstrip("/") + path
        resource = (
            mounted_queryset(space, request.user, traverse=True).filter(path=canonical).first()
        )
        if not resource:
            mount = resolve_space_mount(space.pk, request.user)
            try:
                entry = get_mount_provider("virtual").stat(mount=mount, normalized_path=path)
                observe_virtual_entry(space, entry)
            except Exception:  # noqa: BLE001
                raise exceptions.NotFound() from None
            resource = (
                mounted_queryset(space, request.user, traverse=True).filter(path=canonical).first()
            )
            if not resource:
                raise exceptions.NotFound()
        return response.Response(
            {
                "id": str(resource.pk),
                "space": str(space.pk),
                "href": f"/explorer/resources/{resource.pk}?{urlencode({'space': str(space.pk)})}",
            }
        )
