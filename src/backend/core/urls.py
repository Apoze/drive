"""URL configuration for the core app."""

from django.conf import settings
from django.urls import include, path, re_path

from lasuite.oidc_login.urls import urlpatterns as oidc_urls
from rest_framework.routers import DefaultRouter

from core.api import viewsets
from core.api.docs_documents import (
    DocumentAccessListView,
    DocumentAuthorizationView,
    DocumentCommandView,
    DocumentCopyRequestView,
    DocumentDestinationsView,
    DocumentExportView,
    DocumentInvitationAcceptanceView,
    DocumentInvitationView,
    DocumentLegacyInvitationView,
    DocumentListView,
    DocumentNotificationView,
    DocumentPendingView,
    DocumentPlacementImpactView,
    DocumentQuotaView,
    DocumentRecoveryView,
    DocumentStatusView,
    DocumentUserCommandView,
    DocumentUserStatusView,
    DocumentVisitView,
)
from core.api.messages_files import MessagesFileView
from core.api.storage_admin import (
    StorageAdminJobViewSet,
    StorageConnectionViewSet,
    StorageSpaceAdminViewSet,
)
from core.api.storage_resources import ResourceViewSet, SpaceViewSet
from core.api.storage_transfers import StorageTransferViewSet
from core.api.views_archive_extraction import (
    ArchiveExtractionStartView,
    ArchiveExtractionStatusView,
)
from core.api.views_archive_zip import ArchiveZipStartView, ArchiveZipStatusView
from core.api.views_mount_archive_extraction import MountArchiveExtractionStatusView
from core.api.views_storage_upload import StorageUploadView
from core.external_api import viewsets as external_api_viewsets

# - Main endpoints
router = DefaultRouter()
router.register("items", viewsets.ItemViewSet, basename="items")
router.register("mounts", viewsets.MountViewSet, basename="mounts")
router.register("mount-share-links", viewsets.MountShareLinkViewSet, basename="mount_share_links")
router.register("share-links", viewsets.ShareLinkViewSet, basename="share_links")
router.register("users", viewsets.UserViewSet, basename="users")
router.register("storage-connections", StorageConnectionViewSet, basename="storage_connections")
router.register(
    "storage-administration-jobs", StorageAdminJobViewSet, basename="storage_admin_jobs"
)
router.register("storage-spaces-admin", StorageSpaceAdminViewSet, basename="storage_spaces_admin")
router.register("spaces", SpaceViewSet, basename="spaces")
router.register("resources", ResourceViewSet, basename="resources")
router.register("storage-transfers", StorageTransferViewSet, basename="storage_transfers")

# - Routes nested under a item
item_related_router = DefaultRouter()
item_related_router.register(
    "activity",
    viewsets.ItemActivityViewSet,
    basename="item_activity",
)
item_related_router.register(
    "accesses",
    viewsets.ItemAccessViewSet,
    basename="item_accesses",
)
item_related_router.register(
    "invitations",
    viewsets.InvitationViewset,
    basename="invitations",
)

sdk_relay_router = DefaultRouter()
sdk_relay_router.register(
    "sdk-relay/events",
    viewsets.SDKRelayEventViewset,
    basename="sdk_relay_events",
)

entitlements_router = DefaultRouter()
entitlements_router.register(
    "entitlements",
    viewsets.EntitlementsViewset,
    basename="entitlements",
)

urlpatterns = [
    path(f"api/{settings.API_VERSION}/internal/messages/files/", MessagesFileView.as_view()),
    path(
        f"api/{settings.API_VERSION}/internal/docs/recovery/",
        DocumentRecoveryView.as_view(),
        name="docs-recovery",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/placement-impact/",
        DocumentPlacementImpactView.as_view(),
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/copy/",
        DocumentCopyRequestView.as_view(),
        name="docs-copy",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/export/",
        DocumentExportView.as_view(),
        name="docs-export",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/visit/",
        DocumentVisitView.as_view(),
        name="docs-visit",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/notification-recipients/",
        DocumentNotificationView.as_view(),
        name="docs-notification-recipients",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/invitations/",
        DocumentInvitationView.as_view(),
        name="docs-invitations",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/invitations/legacy/",
        DocumentLegacyInvitationView.as_view(),
        name="docs-invitation-legacy",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/invitations/accept/",
        DocumentInvitationAcceptanceView.as_view(),
        name="docs-invitation-accept",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/pending/",
        DocumentPendingView.as_view(),
        name="docs-pending",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/destinations/",
        DocumentDestinationsView.as_view(),
        name="docs_destinations",
    ),
    path(
        f"api/{settings.API_VERSION}/documents/command/",
        DocumentUserCommandView.as_view(),
        name="document_user_command",
    ),
    path(
        f"api/{settings.API_VERSION}/documents/status/",
        DocumentUserStatusView.as_view(),
        name="document_user_status",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/quota/",
        DocumentQuotaView.as_view(),
        name="docs_quota",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/accesses/",
        DocumentAccessListView.as_view(),
        name="docs_accesses",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/status/",
        DocumentStatusView.as_view(),
        name="docs_status",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/command/",
        DocumentCommandView.as_view(),
        name="docs_command",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/list/",
        DocumentListView.as_view(),
        name="docs_list",
    ),
    path(
        f"api/{settings.API_VERSION}/internal/docs/authorize/",
        DocumentAuthorizationView.as_view(),
        name="docs_authorize",
    ),
    path(f"api/{settings.API_VERSION}/suite/", include("suite_identity.urls")),
    path(
        f"api/{settings.API_VERSION}/",
        include(
            [
                *router.urls,
                path(
                    "storage-uploads/<uuid:item_id>/",
                    StorageUploadView.as_view(),
                    name="storage_upload",
                ),
                *oidc_urls,
                re_path(
                    r"^items/(?P<resource_id>[0-9a-z-]*)/",
                    include(item_related_router.urls),
                ),
                path(
                    "user-reconciliations/<str:user_type>/<str:confirmation_id>/",
                    viewsets.ReconciliationConfirmView.as_view(),
                ),
                *sdk_relay_router.urls,
                *entitlements_router.urls,
                path("archive-extractions/", ArchiveExtractionStartView.as_view()),
                path(
                    "archive-extractions/<uuid:job_id>/",
                    ArchiveExtractionStatusView.as_view(),
                ),
                path(
                    "mount-archive-extractions/<uuid:job_id>/",
                    MountArchiveExtractionStatusView.as_view(),
                ),
                path(
                    "mount-stream/<str:token>/",
                    viewsets.MountStreamView.as_view(),
                    name="mount_stream",
                ),
                path("archive-zips/", ArchiveZipStartView.as_view()),
                path("archive-zips/<uuid:job_id>/", ArchiveZipStatusView.as_view()),
            ]
        ),
    ),
    path(f"api/{settings.API_VERSION}/config/", viewsets.ConfigView.as_view()),
]


if settings.OIDC_RESOURCE_SERVER_ENABLED:
    # - Resource server routes
    external_api_router = DefaultRouter()
    items_access_config = settings.EXTERNAL_API.get("items", {})
    items_enabled = bool(items_access_config.get("enabled", False))
    if items_enabled:
        external_api_router.register(
            "items",
            external_api_viewsets.ResourceServerItemViewSet,
            basename="resource_server_items",
        )

    users_access_config = settings.EXTERNAL_API.get("users", {})
    if users_access_config.get("enabled", False):
        external_api_router.register(
            "users",
            external_api_viewsets.ResourceServerUserViewSet,
            basename="resource_server_users",
        )

    external_api_urls = [*external_api_router.urls]

    if items_enabled:
        # - Resource server nested routes under items
        external_api_item_related_router = DefaultRouter()
        item_access_config = settings.EXTERNAL_API.get("item_access", {})
        if item_access_config.get("enabled", False):
            external_api_item_related_router.register(
                "accesses",
                external_api_viewsets.ResourceServerItemAccessViewSet,
                basename="resource_server_item_accesses",
            )

        item_invitation_config = settings.EXTERNAL_API.get("item_invitation", {})
        if item_invitation_config.get("enabled", False):
            external_api_item_related_router.register(
                "invitations",
                external_api_viewsets.ResourceServerInvitationViewSet,
                basename="resource_server_invitations",
            )

        if external_api_item_related_router.urls:
            external_api_urls.append(
                re_path(
                    r"^items/(?P<resource_id>[0-9a-z-]*)/",
                    include(external_api_item_related_router.urls),
                )
            )

    if external_api_urls:
        urlpatterns.append(
            path(
                f"external_api/{settings.API_VERSION}/",
                include(external_api_urls),
            )
        )

if settings.METRICS_ENABLED:
    usage_metrics_router = DefaultRouter()
    usage_metrics_router.register(
        "usage",
        viewsets.UsageMetricViewset,
        basename="usage_metrics",
    )
    urlpatterns.append(
        path(
            f"external_api/{settings.API_VERSION}/metrics/",
            include(usage_metrics_router.urls),
        )
    )
