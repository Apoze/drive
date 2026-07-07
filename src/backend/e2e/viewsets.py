"""Viewsets for the e2e app."""

import io
import urllib.parse

from django.conf import settings
from django.contrib.auth import login
from django.core.management import call_command
from django.db import connection
from django.http import Http404, HttpResponseRedirect
from django.middleware.csrf import get_token

import rest_framework as drf
from rest_framework import response as drf_response
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from e2e.authentication import ServerToServerAuthentication
from e2e.serializers import (
    E2EAuthSerializer,
    E2EBootstrapScenarioSerializer,
    E2EBootstrapSessionSerializer,
    E2ECleanupScopeSerializer,
)
from e2e.services.bootstrap import E2EBootstrapService
from e2e.utils import (
    DEFAULT_E2E_LANGUAGE,
    ensure_main_workspace,
    get_or_create_e2e_user,
)

QA_BROWSER_BOOTSTRAP_RUN_ID = "qa-lan-browser"
QA_BROWSER_BOOTSTRAP_WORKER_ID = "manual-browser"
QA_BROWSER_BOOTSTRAP_ACTOR_KEY = "primary"
QA_BROWSER_BOOTSTRAP_REGULAR_SCENARIO_ID = "folder-export"
QA_BROWSER_BOOTSTRAP_MOUNT_SCENARIO_ID = "mount-browser"
QA_BROWSER_BOOTSTRAP_CONVERSION_SCENARIO_ID = "legacy-conversion-browser"


def _frontend_origin() -> str:
    """Return the browser-facing frontend origin from the dev login config."""
    configured = str(getattr(settings, "LOGIN_REDIRECT_URL", "") or "").strip()
    parsed = urllib.parse.urlsplit(configured)
    if not parsed.scheme or not parsed.netloc:
        return "http://localhost:3000"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _frontend_url(path: str) -> str:
    return f"{_frontend_origin()}{path}"


def _wants_conversion_fixture(request) -> bool:
    value = str(request.GET.get("include_conversion") or "").strip().lower()
    return value in {"1", "true", "yes"}


def _mount_route(*, mount_id: str, root_path: str) -> str:
    query = ""
    if root_path and root_path != "/":
        query = "?" + urllib.parse.urlencode({"path": root_path})
    return f"/explorer/mounts/{mount_id}{query}"


class UserAuthViewSet(drf.viewsets.ViewSet):
    """Legacy readiness-only auth bootstrap for transitional Playwright coverage."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request):
        """
        POST /api/v1.0/e2e/user-auth/
        Legacy transitional endpoint:
        create a user with the given email if it doesn't exist and log them in.

        Normal product specs should use `/bootstrap-session/` instead.
        """
        serializer = E2EAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_or_create_e2e_user(
            serializer.validated_data["email"],
            language=None,
        )

        login(request, user, "django.contrib.auth.backends.ModelBackend")
        ensure_main_workspace(user)
        # Ensure the CSRF cookie is set for subsequent SPA mutations.
        # This endpoint is called via Playwright's APIRequestContext (not subject to CORS),
        # so setting the cookie here is the most reliable way to bootstrap the browser state.
        get_token(request)

        return drf_response.Response({"email": user.email}, status=status.HTTP_200_OK)


class BootstrapSessionAPIView(APIView):
    """
    POST /api/v1.0/e2e/bootstrap-session/
    Create or reuse a deterministic actor session for one E2E worker.

    Auth: Server-to-server bearer token.
    """

    permission_classes = [AllowAny]
    authentication_classes = [ServerToServerAuthentication]

    def post(self, request):
        """Create or reuse a deterministic actor, workspace, and browser session."""
        serializer = E2EBootstrapSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = E2EBootstrapService()
        validated = serializer.validated_data
        result = service.bootstrap_session(
            run_id=validated["run_id"],
            worker_id=validated["worker_id"],
            actor_key=validated["actor_key"],
            email=validated.get("email"),
            language=validated["language"] if "language" in validated else DEFAULT_E2E_LANGUAGE,
            full_name=validated.get("full_name"),
            short_name=validated.get("short_name"),
        )

        user = result["user"]
        login(request, user, "django.contrib.auth.backends.ModelBackend")
        csrf_token = get_token(request)

        payload = result["response"]
        payload["session"] = {
            "authenticated": True,
            "csrf_cookie_name": "csrftoken",
            "csrf_cookie_present": bool(csrf_token),
        }
        return drf_response.Response(payload, status=status.HTTP_200_OK)


class QABrowserBootstrapAPIView(APIView):
    """
    GET /api/v1.0/e2e/qa-browser-bootstrap/
    Dev-only LAN browser QA bootstrap.

    This endpoint intentionally does not expose the server-to-server token or a
    password. It reuses deterministic E2E dummy actors with unusable passwords,
    creates QA fixture data, logs the browser into that dummy account, and
    redirects to the regular Drive fixture folder.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        """Create deterministic QA fixtures, set a browser session, and redirect."""
        if not settings.LOAD_E2E_URLS:
            raise Http404

        service = E2EBootstrapService()
        session = service.bootstrap_session(
            run_id=QA_BROWSER_BOOTSTRAP_RUN_ID,
            worker_id=QA_BROWSER_BOOTSTRAP_WORKER_ID,
            actor_key=QA_BROWSER_BOOTSTRAP_ACTOR_KEY,
            language=DEFAULT_E2E_LANGUAGE,
        )
        regular_fixture = service.bootstrap_scenario(
            kind="search_dataset",
            run_id=QA_BROWSER_BOOTSTRAP_RUN_ID,
            worker_id=QA_BROWSER_BOOTSTRAP_WORKER_ID,
            actor_key=QA_BROWSER_BOOTSTRAP_ACTOR_KEY,
            scenario_id=QA_BROWSER_BOOTSTRAP_REGULAR_SCENARIO_ID,
        )

        mount_fixture = None
        mount_status = "unavailable"
        try:
            mount_fixture = service.bootstrap_scenario(
                kind="mount_subtree",
                run_id=QA_BROWSER_BOOTSTRAP_RUN_ID,
                worker_id=QA_BROWSER_BOOTSTRAP_WORKER_ID,
                actor_key=QA_BROWSER_BOOTSTRAP_ACTOR_KEY,
                scenario_id=QA_BROWSER_BOOTSTRAP_MOUNT_SCENARIO_ID,
            )
            mount_status = "ready"
        except serializers.ValidationError:
            mount_status = "unavailable"

        user = session["user"]
        login(request, user, "django.contrib.auth.backends.ModelBackend")
        get_token(request)

        regular_root = regular_fixture["result"]["dataset_root"]
        regular_route = f"/explorer/items/{regular_root['id']}"
        response = HttpResponseRedirect(_frontend_url(regular_route))
        response["Cache-Control"] = "no-store"
        response["X-QA-Bootstrap-Regular-Url"] = _frontend_url(regular_route)
        response["X-QA-Bootstrap-Regular-Title"] = str(regular_root["title"])
        response["X-QA-Bootstrap-Mount-Status"] = mount_status

        if mount_fixture is not None:
            mount_result = mount_fixture["result"]
            mount_route = _mount_route(
                mount_id=str(mount_result["mount_id"]),
                root_path=str(mount_result["root_path"]),
            )
            response["X-QA-Bootstrap-Mount-Url"] = _frontend_url(mount_route)

        if _wants_conversion_fixture(request):
            conversion_fixture = service.bootstrap_scenario(
                kind="legacy_conversion_fixture",
                run_id=QA_BROWSER_BOOTSTRAP_RUN_ID,
                worker_id=QA_BROWSER_BOOTSTRAP_WORKER_ID,
                actor_key=QA_BROWSER_BOOTSTRAP_ACTOR_KEY,
                scenario_id=QA_BROWSER_BOOTSTRAP_CONVERSION_SCENARIO_ID,
            )
            conversion_result = conversion_fixture["result"]
            conversion_root = conversion_result["conversion_root"]
            legacy_file = conversion_result["legacy_file"]
            can_convert = bool(legacy_file["abilities"]["convert"])
            response["X-QA-Bootstrap-Conversion-Status"] = "ready" if can_convert else "disabled"
            response["X-QA-Bootstrap-Conversion-Url"] = _frontend_url(
                f"/explorer/items/{conversion_root['id']}"
            )
            response["X-QA-Bootstrap-Conversion-Title"] = str(legacy_file["title"])
            response["X-QA-Bootstrap-Conversion-Item-Id"] = str(legacy_file["id"])
            response["X-QA-Bootstrap-Conversion-Ability"] = "convert" if can_convert else "missing"

        return response


class BootstrapScenarioAPIView(APIView):
    """
    POST /api/v1.0/e2e/bootstrap-scenario/
    Seed one deterministic E2E scenario scope.

    Auth: Server-to-server bearer token.
    """

    permission_classes = [AllowAny]
    authentication_classes = [ServerToServerAuthentication]

    def post(self, request):
        """Seed namespaced test data without truncating the full database."""
        serializer = E2EBootstrapScenarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        service = E2EBootstrapService()
        payload = service.bootstrap_scenario(
            kind=validated["kind"],
            run_id=validated["run_id"],
            worker_id=validated["worker_id"],
            actor_key=validated["actor_key"],
            scenario_id=validated["scenario_id"],
            secondary_actor_key=validated.get("secondary_actor_key", "secondary"),
            mount_id=validated.get("mount_id"),
        )
        return drf_response.Response(payload, status=status.HTTP_200_OK)


class CleanupScopeAPIView(APIView):
    """
    POST /api/v1.0/e2e/cleanup-scope/
    Delete one run / worker / scenario namespace precisely.

    Auth: Server-to-server bearer token.
    """

    permission_classes = [AllowAny]
    authentication_classes = [ServerToServerAuthentication]

    def post(self, request):
        """Delete only the requested E2E scope without truncating the database."""
        serializer = E2ECleanupScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = E2EBootstrapService()
        payload = service.cleanup_scope(**serializer.validated_data)
        return drf_response.Response(payload, status=status.HTTP_200_OK)


def _quote_ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


class ClearDbAPIView(APIView):
    """
    POST /api/v1.0/e2e/clear-db/
    Legacy readiness-only endpoint that truncates application tables.

    Auth: Server-to-server bearer token (see SERVER_TO_SERVER_API_TOKENS).
    """

    permission_classes = [AllowAny]
    authentication_classes = [ServerToServerAuthentication]

    def post(self, request):
        """Truncate application tables for E2E legacy readiness checks only."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename NOT IN ('django_migrations', 'django_site')
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            if tables:
                stmt = "TRUNCATE TABLE " + ", ".join(_quote_ident(t) for t in tables) + " CASCADE"
                cursor.execute(stmt)

        return drf_response.Response(
            {"cleared_table_count": len(tables)},
            status=status.HTTP_200_OK,
        )


class RunFixtureAPIView(APIView):
    """
    POST /api/v1.0/e2e/run-fixture/
    Run an allowlisted E2E fixture command.

    Auth: Server-to-server bearer token (see SERVER_TO_SERVER_API_TOKENS).
    """

    permission_classes = [AllowAny]
    authentication_classes = [ServerToServerAuthentication]

    ALLOWLIST = {"e2e_fixture_search"}

    def post(self, request):
        """Run an allowlisted E2E fixture command."""
        fixture = request.data.get("fixture")
        if not fixture or not isinstance(fixture, str):
            return drf_response.Response(
                {"detail": "Missing fixture."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fixture not in self.ALLOWLIST:
            return drf_response.Response(
                {"detail": "Fixture not allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stdout = io.StringIO()
        stderr = io.StringIO()
        call_command(fixture, stdout=stdout, stderr=stderr)

        return drf_response.Response(
            {"fixture": fixture, "status": "ok"},
            status=status.HTTP_200_OK,
        )
