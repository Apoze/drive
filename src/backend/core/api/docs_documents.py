"""Private Docs authorization API; a service key never replaces actor permissions."""

from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import Exists, OuterRef, Subquery

from rest_framework import exceptions, permissions, response, serializers, views

from core.models import DocsBinding, Item, ItemFavorite, LinkTrace
from core.services.docs_lifecycle import change_document, command_status, pending_creations
from core.services.docs_resources import (
    access_ttl,
    document_abilities,
    document_page,
    enabled,
    role_for_document,
    visible_documents,
)
from core.services.docs_sharing import access_page, notification_recipients


class DocumentCopyRequestSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    request_key = serializers.UUIDField()
    destination = serializers.UUIDField(required=False)
    space_id = serializers.UUIDField(required=False, allow_null=True)
    with_accesses = serializers.BooleanField(default=False)


def request_copy(user, data):
    """Both native menus start the same resumable copy, never a binary duplicate."""
    from core.services.docs_jobs import enqueue  # noqa: PLC0415
    from core.services.storage_move_job import execute_move  # noqa: PLC0415
    from core.services.storage_transfer_location import resolve_location  # noqa: PLC0415

    binding = (
        DocsBinding.objects.select_related("item").filter(document_id=data["document_id"]).first()
    )
    if not binding or not binding.item_id:
        raise exceptions.NotFound()
    item = binding.item
    destination_id = data.get("destination") or (
        item.parent().pk if item.depth > 1 else binding.mounted_parent_id
    )
    if not destination_id:
        raise exceptions.ValidationError("Choose a destination in Drive.")
    job = enqueue(
        user,
        resolve_location(item.pk, user),
        resolve_location(
            destination_id,
            user,
            space_id=data.get("space_id") or binding.anchor_space_id,
            destination=True,
            allow_document=True,
        ),
        mode="copy",
        request_key=data["request_key"],
        with_accesses=data["with_accesses"],
    )
    execute_move(job.pk)
    job.refresh_from_db()
    result = job.payload.get("result")
    copied = DocsBinding.objects.filter(item_id=result).first() if result else None
    return {
        "job_id": str(job.pk),
        "state": job.state,
        "reason": job.reason,
        "id": str(copied.document_id) if copied else None,
        "item_id": result,
    }


class DocumentCopyRequestView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        serializer = DocumentCopyRequestSerializer(data=receive(request, purpose="mutation"))
        serializer.is_valid(raise_exception=True)
        result = request_copy(request.user, serializer.validated_data)
        return response.Response(result, status=201 if result["state"] == "done" else 202)


class DocumentPlacementSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    destination = serializers.UUIDField()
    space_id = serializers.UUIDField(required=False, allow_null=True)


class DocumentPlacementImpactView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Reuse the same authorized impact calculation as Drive's transfer picker."""
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.storage_transfer_impact import transfer_impact  # noqa: PLC0415
        from core.services.storage_transfer_location import resolve_location  # noqa: PLC0415

        if not enabled():
            raise exceptions.NotFound()
        serializer = DocumentPlacementSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        binding = DocsBinding.objects.filter(document_id=data["document_id"]).first()
        if not binding or not binding.item_id:
            raise exceptions.NotFound()
        source = resolve_location(binding.item_id, request.user)
        destination = resolve_location(
            data["destination"],
            request.user,
            space_id=data.get("space_id"),
            destination=True,
            allow_document=True,
        )
        return response.Response(transfer_impact([source], destination, request.user, "move"))


class DocumentExportSerializer(serializers.Serializer):
    """A private native PDF, with its source revision and immutable upload intent."""

    document_id = serializers.UUIDField()
    destination = serializers.UUIDField()
    space_id = serializers.UUIDField(allow_null=True, required=False)
    request_key = serializers.UUIDField()
    revision = serializers.IntegerField(min_value=1)
    version = serializers.CharField(max_length=255, allow_blank=True)
    size = serializers.IntegerField(min_value=5, max_value=128 * 1024 * 1024)
    digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z")
    name = serializers.CharField(max_length=255)


class DocumentExportView(views.APIView):
    """Keep the file body streamed; a peer key still requires a verified person."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    parser_classes = []

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_exports import export_file  # noqa: PLC0415

        serializer = DocumentExportSerializer(
            data=receive(request, purpose="mutation", streaming=True)
        )
        serializer.is_valid(raise_exception=True)
        result = export_file(request.user, serializer.validated_data, request.stream)
        return response.Response(
            result,
            status=201 if result["state"] == "done" else 202,
            headers={"Cache-Control": "no-store"},
        )


class DocumentIdsSerializer(serializers.Serializer):
    """Keep each remote permission check bounded, including denied identifiers."""

    document_ids = serializers.ListField(
        child=serializers.UUIDField(), max_length=100, allow_empty=False
    )


class DocumentVisitSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()


class DocumentVisitView(views.APIView):
    """A deliberate opening in Docs updates Drive recents, never a permission poll."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from django.utils import timezone  # noqa: PLC0415

        from suite_identity.document_transport import receive  # noqa: PLC0415

        serializer = DocumentVisitSerializer(data=receive(request, purpose="mutation"))
        serializer.is_valid(raise_exception=True)
        binding = (
            DocsBinding.objects.select_related("item")
            .filter(document_id=serializer.validated_data["document_id"])
            .first()
        )
        if (
            binding is None
            or binding.item is None
            or not document_abilities(binding.item, request.user).get("retrieve")
        ):
            raise exceptions.NotFound()
        if request.user.is_authenticated:
            LinkTrace.objects.update_or_create(
                item=binding.item, user=request.user, defaults={"updated_at": timezone.now()}
            )
        return response.Response({"state": "recorded"}, headers={"Cache-Control": "no-store"})


class DocumentPageSerializer(serializers.Serializer):
    offset = serializers.IntegerField(min_value=0, default=0)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=50)


class DocumentDestinationsSerializer(DocumentPageSerializer):
    space_id = serializers.UUIDField(required=False)
    parent_id = serializers.UUIDField(required=False)


class DocumentPendingView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        serializer = DocumentPageSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        return response.Response(
            pending_creations(request.user, **serializer.validated_data),
            headers={"Cache-Control": "no-store"},
        )


class DocumentRecoveryView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_anchors import recovery_page  # noqa: PLC0415

        if not enabled():
            raise exceptions.NotFound()
        serializer = DocumentPageSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        return response.Response(
            recovery_page(request.user, **serializer.validated_data),
            headers={"Cache-Control": "no-store"},
        )


class DocumentInvitationQuerySerializer(DocumentPageSerializer):
    document_id = serializers.UUIDField()
    invitation_id = serializers.UUIDField(required=False)
    email = serializers.EmailField(required=False)


class DocumentInvitationView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_invitations import page  # noqa: PLC0415

        serializer = DocumentInvitationQuerySerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data
        binding = (
            DocsBinding.objects.select_related("item")
            .filter(document_id=query["document_id"])
            .first()
        )
        if binding is None or binding.item is None:
            raise exceptions.NotFound()
        return response.Response(
            page(binding.item, request.user, query), headers={"Cache-Control": "no-store"}
        )


class DocumentInvitationAcceptanceSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=1024, trim_whitespace=False)


class DocumentInvitationAcceptanceView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_invitations import accept  # noqa: PLC0415

        serializer = DocumentInvitationAcceptanceSerializer(
            data=receive(request, purpose="mutation")
        )
        serializer.is_valid(raise_exception=True)
        return response.Response(
            accept(request.user, serializer.validated_data["token"]),
            headers={"Cache-Control": "no-store"},
        )


class DocumentDestinationsView(views.APIView):
    """The private read peer can list only the actual actor's permitted destinations."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_destinations import destinations  # noqa: PLC0415

        serializer = DocumentDestinationsSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        return response.Response(
            destinations(request.user, serializer.validated_data),
            headers={"Cache-Control": "no-store"},
        )


class DocumentQuotaSerializer(serializers.Serializer):
    """Accept bounded metadata, never document contents or native storage keys."""

    action = serializers.ChoiceField(choices=["reserve", "begin", "commit", "cancel", "reduce"])
    document_id = serializers.UUIDField()
    operation_id = serializers.UUIDField(required=False)
    size = serializers.IntegerField(min_value=0, max_value=2**53 - 1, required=False)
    version = serializers.CharField(max_length=255, allow_blank=True, required=False)
    digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z", required=False)
    unpublished = serializers.BooleanField(default=False)

    def validate(self, attrs):
        required = {
            "reserve": ("size",),
            "begin": ("size", "version", "digest"),
            "commit": ("size", "version", "digest"),
            "cancel": (),
            "reduce": ("size", "version"),
        }[attrs["action"]]
        if attrs["action"] != "reduce":
            required = (*required, "operation_id")
        for field in required:
            if field not in attrs:
                raise serializers.ValidationError({field: "This field is required."})
        if attrs["unpublished"] and (attrs["action"] != "cancel" or "version" not in attrs):
            raise serializers.ValidationError(
                "Only a verified cancellation can rule out publication."
            )
        return attrs


class DocumentQuotaView(views.APIView):
    """The mutation peer can settle journaled bytes, never charge arbitrary files."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_quota import transition  # noqa: PLC0415

        payload = receive(request, purpose="mutation")
        serializer = DocumentQuotaSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return response.Response(
            transition(request.user, serializer.validated_data),
            headers={"Cache-Control": "no-store"},
        )


class DocumentAuthorizationView(views.APIView):
    """Resolve current Drive grants without accepting cookies or user-sub headers."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Each result discloses metadata only after its current access check."""
        # Imported at call time so disabled installations need no peer configuration.
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        body = receive(request, purpose="read")
        serializer = DocumentIdsSerializer(data=body)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["document_ids"]
        bindings = {
            binding.document_id: binding
            for binding in DocsBinding.objects.filter(document_id__in=ids)
            .select_related("item")
            .annotate(
                parent_item_id=Subquery(
                    Item.objects.filter(path__ancestors=OuterRef("item__path"))
                    .exclude(pk=OuterRef("item_id"))
                    .order_by("-path")
                    .values("pk")[:1]
                ),
                favorite=Exists(
                    ItemFavorite.objects.filter(
                        item_id=OuterRef("item_id"), user_id=request.user.pk
                    )
                ),
            )
        }
        with document_page(
            [binding.item for binding in bindings.values() if binding.item_id], request.user
        ):
            result = {}
            for document_id in ids:
                binding = bindings.get(document_id)
                record = {"abilities": {}, "role": None}
                if binding and binding.item_id:
                    item = binding.item
                    abilities = document_abilities(item, request.user)
                    if abilities.get("retrieve"):
                        record = {
                            "abilities": abilities,
                            "access_ttl": access_ttl(item),
                            "role": role_for_document(item, request.user),
                            "item_id": str(item.pk),
                            "destination": str(binding.parent_item_id)
                            if binding.parent_item_id
                            else str(binding.mounted_parent_id)
                            if binding.mounted_parent_id
                            else None,
                            "destination_space": str(binding.anchor_space_id)
                            if binding.anchor_space_id
                            else None,
                            "revision": binding.revision,
                            "state": binding.state,
                            "title": item.title,
                            "created_at": item.created_at,
                            "updated_at": item.updated_at,
                            "link_reach": item.link_reach or "restricted",
                            "link_role": item.link_role,
                            "is_favorite": binding.favorite,
                            "deleted_at": item.deleted_at,
                            "ancestors_deleted_at": item.ancestors_deleted_at,
                        }
                result[str(document_id)] = record
            return response.Response(result, headers={"Cache-Control": "no-store"})


class DocumentListSerializer(serializers.Serializer):
    """The authority filters and counts; a client cannot count inaccessible rows."""

    offset = serializers.IntegerField(min_value=0, default=0)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=50)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    trash = serializers.BooleanField(default=False)
    parent_document_id = serializers.UUIDField(required=False)
    descendants = serializers.BooleanField(default=False)
    roots_only = serializers.BooleanField(default=True)
    is_creator_me = serializers.BooleanField(required=False)
    is_favorite = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(
        choices=[
            "title",
            "-title",
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
            "deleted_at",
            "-deleted_at",
            "path",
        ],
        default="-updated_at",
    )


class DocumentListView(views.APIView):
    """Bounded listing for Docs backed by current Drive permissions."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        body = receive(request, purpose="read")
        serializer = DocumentListSerializer(data=body)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data
        items = visible_documents(request.user, query)
        count = items.count()
        offset = query["offset"]
        ordering = query["ordering"]
        if ordering == "path":
            ancestors = (
                DocsBinding.objects.filter(item__path__ancestors=OuterRef("path"))
                .order_by("item__path")
                .values("sort_order")
            )
            items = items.alias(document_order=ArraySubquery(ancestors))
            ordering = "document_order"
        page = (
            items.annotate_is_favorite(request.user)
            .select_related("docs_binding")
            .order_by(ordering, "path")[offset : offset + query["limit"]]
        )
        page = list(page)
        with document_page(page, request.user):
            return response.Response(
                {
                    "count": count,
                    "results": [
                        {
                            "document_id": str(item.docs_binding.document_id),
                            "item_id": str(item.pk),
                            "title": item.title,
                            "created_at": item.created_at,
                            "updated_at": item.updated_at,
                            "link_reach": item.link_reach or "restricted",
                            "link_role": item.link_role,
                            "is_favorite": item.is_favorite,
                            "revision": item.docs_binding.revision,
                            "deleted_at": item.deleted_at,
                            "ancestors_deleted_at": item.ancestors_deleted_at,
                            "role": role_for_document(item, request.user),
                            "abilities": document_abilities(item, request.user),
                        }
                        for item in page
                    ],
                },
                headers={"Cache-Control": "no-store"},
            )


class InitialDocumentContentSerializer(serializers.Serializer):
    """Bind a creation retry to its content without transporting that content."""

    size = serializers.IntegerField(min_value=0, max_value=2**53 - 1)
    digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z")


class DocumentCommandSerializer(serializers.Serializer):
    """Only explicit document operations cross the private mutation boundary."""

    action = serializers.ChoiceField(
        choices=[
            "create",
            "cancel_creation",
            "rename",
            "move",
            "recover",
            "trash",
            "restore",
            "favorite",
            "link_configuration",
            "grant_access",
            "update_access",
            "revoke_access",
            "invite",
            "update_invitation",
            "revoke_invitation",
            "resend_invitation",
        ]
    )
    document_id = serializers.UUIDField(required=False)
    initial_content = InitialDocumentContentSerializer(required=False)
    request_key = serializers.UUIDField(required=False)
    creation_key = serializers.UUIDField(required=False)
    destination = serializers.UUIDField(required=False)
    relative_document_id = serializers.UUIDField(required=False)
    position = serializers.ChoiceField(
        choices=["first-child", "last-child", "left", "right", "first-sibling", "last-sibling"],
        default="last-child",
    )
    space_id = serializers.UUIDField(required=False, allow_null=True)
    revision = serializers.IntegerField(min_value=1, required=False)
    title = serializers.CharField(max_length=255, required=False, allow_blank=False)
    favorite = serializers.BooleanField(required=False)
    access_id = serializers.UUIDField(required=False)
    principal_id = serializers.UUIDField(required=False)
    group_id = serializers.UUIDField(required=False)
    invitation_id = serializers.UUIDField(required=False)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(
        choices=["reader", "commenter", "editor", "administrator", "owner"], required=False
    )
    link_reach = serializers.ChoiceField(
        choices=["restricted", "authenticated", "public"], required=False
    )
    link_role = serializers.ChoiceField(choices=["reader", "commenter", "editor"], required=False)

    def validate(self, attrs):
        if "creation_key" in attrs and attrs["action"] != "cancel_creation":
            raise serializers.ValidationError("A creation key belongs to cancellation only.")
        if "email" in attrs and attrs["action"] != "invite":
            raise serializers.ValidationError("Revoke an invitation before changing its recipient.")
        if "initial_content" in attrs and attrs["action"] != "create":
            raise serializers.ValidationError("Initial content belongs to creation only.")
        required = [] if attrs["action"] == "create" else ["document_id"]
        required += {
            "create": ["request_key", "destination", "title"],
            "rename": ["title"],
            "move": ["destination", "request_key"],
            "recover": ["destination", "request_key", "revision"],
            "cancel_creation": ["request_key"],
            "favorite": ["favorite"],
            "grant_access": ["role"],
            "update_access": ["access_id", "role"],
            "revoke_access": ["access_id"],
            "invite": ["email", "role", "request_key"],
            "update_invitation": ["invitation_id", "request_key", "role"],
            "revoke_invitation": ["invitation_id", "request_key"],
            "resend_invitation": ["invitation_id", "request_key"],
        }.get(attrs["action"], [])
        if attrs["action"] == "grant_access" and bool(attrs.get("principal_id")) == bool(
            attrs.get("group_id")
        ):
            raise serializers.ValidationError("Choose exactly one person or group.")
        if attrs["action"] == "link_configuration" and not (
            "link_reach" in attrs or "link_role" in attrs
        ):
            raise serializers.ValidationError("Specify a link reach or role.")
        for field in required:
            if field not in attrs:
                raise serializers.ValidationError({field: "This field is required."})
        return attrs


class DocumentCommandView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        payload = receive(request, purpose="mutation")
        if not request.user.is_authenticated:
            raise exceptions.PermissionDenied()
        serializer = DocumentCommandSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        result = change_document(request.user, serializer.validated_data)
        pending = result["revision"] != result["applied_revision"] or result["state"] in {
            "pending",
            "preparing",
        }
        return response.Response(
            result, status=202 if pending else 200, headers={"Cache-Control": "no-store"}
        )


class DocumentStatusSerializer(serializers.Serializer):
    request_key = serializers.UUIDField()


class DocumentUserCommandView(views.APIView):
    """Drive's Web UI uses the same authority with its ordinary authenticated session."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        serializer = DocumentCommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = change_document(request.user, serializer.validated_data)
        pending = result["revision"] != result["applied_revision"] or result["state"] in {
            "pending",
            "preparing",
        }
        return response.Response(
            result,
            status=202 if pending else 200,
            headers={"Cache-Control": "no-store"},
        )


class DocumentUserStatusView(views.APIView):
    """Only the initiating principal can inspect an operation from the Web UI."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = DocumentStatusSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return response.Response(
            command_status(request.user, serializer.validated_data["request_key"]),
            headers={"Cache-Control": "no-store"},
        )


class DocumentAccessListSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    access_id = serializers.UUIDField(required=False)
    principal_id = serializers.UUIDField(required=False)
    group_id = serializers.UUIDField(required=False)
    offset = serializers.IntegerField(min_value=0, default=0)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=100)


class DocumentAccessListView(views.APIView):
    """Sharing metadata is paged and authorized independently of the peer key."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        serializer = DocumentAccessListSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data
        binding = (
            DocsBinding.objects.select_related("item")
            .filter(
                document_id=query["document_id"],
                item__isnull=False,
            )
            .first()
        )
        if binding is None:
            raise exceptions.NotFound()
        return response.Response(
            access_page(
                binding.item,
                request.user,
                **{field: value for field, value in query.items() if field != "document_id"},
            ),
            headers={"Cache-Control": "no-store"},
        )


class DocumentStatusView(views.APIView):
    """Read-only recovery of an operation's receipt, without replaying a mutation."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        serializer = DocumentStatusSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        result = command_status(request.user, serializer.validated_data["request_key"])
        return response.Response(result, headers={"Cache-Control": "no-store"})


class DocumentNotificationSerializer(DocumentPageSerializer):
    document_id = serializers.UUIDField()
    requester_principal = serializers.UUIDField()


class DocumentNotificationView(views.APIView):
    """Service-only recipient lookup, never exposed by the native public API."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not enabled():
            raise exceptions.NotFound()
        from suite_identity.document_transport import receive  # noqa: PLC0415

        serializer = DocumentNotificationSerializer(data=receive(request, purpose="read"))
        serializer.is_valid(raise_exception=True)
        if request.user.is_authenticated:
            raise exceptions.PermissionDenied("This route is reserved for the notification worker.")
        return response.Response(
            notification_recipients(**serializer.validated_data),
            headers={"Cache-Control": "no-store"},
        )


class DocumentLegacyInvitationView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from suite_identity.document_transport import receive  # noqa: PLC0415

        from core.services.docs_invitations import legacy_offer  # noqa: PLC0415

        data = receive(request, purpose="read")
        identifier = serializers.UUIDField().run_validation(data.get("document_id"))
        return response.Response(
            legacy_offer(request.user, identifier), headers={"Cache-Control": "no-store"}
        )
