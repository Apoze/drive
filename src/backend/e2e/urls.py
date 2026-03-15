"""URL configuration for the e2e app."""

from django.conf import settings
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from e2e import viewsets

user_auth_router = DefaultRouter()
user_auth_router.register(
    "user-auth",
    viewsets.UserAuthViewSet,
    basename="user-auth",
)

urlpatterns = [
    path(
        f"api/{settings.API_VERSION}/e2e/",
        include(
            [
                # Legacy readiness/transitional endpoints remain mounted here until the
                # independent suite fully retires DB-global bootstrap controls.
                *user_auth_router.urls,
                path(
                    "clear-db/", viewsets.ClearDbAPIView.as_view(), name="e2e-clear-db"
                ),
                path(
                    "bootstrap-session/",
                    viewsets.BootstrapSessionAPIView.as_view(),
                    name="e2e-bootstrap-session",
                ),
                path(
                    "bootstrap-scenario/",
                    viewsets.BootstrapScenarioAPIView.as_view(),
                    name="e2e-bootstrap-scenario",
                ),
                path(
                    "cleanup-scope/",
                    viewsets.CleanupScopeAPIView.as_view(),
                    name="e2e-cleanup-scope",
                ),
                path(
                    "run-fixture/",
                    viewsets.RunFixtureAPIView.as_view(),
                    name="e2e-run-fixture",
                ),
            ]
        ),
    ),
]
