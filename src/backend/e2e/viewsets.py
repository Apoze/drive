"""Viewsets for the e2e app."""

import io

from django.contrib.auth import login
from django.core.management import call_command
from django.db import connection
from django.middleware.csrf import get_token

import rest_framework as drf
from rest_framework import response as drf_response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core import models
from core.authentication import ServerToServerAuthentication

from e2e.serializers import E2EAuthSerializer
from e2e.utils import ensure_main_workspace


class UserAuthViewSet(drf.viewsets.ViewSet):
    """Viewset to handle user authentication"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request):
        """
        POST /api/v1.0/e2e/user-auth/
        Create a user with the given email if it doesn't exist and log them in
        """
        serializer = E2EAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create user if doesn't exist
        user = models.User.objects.filter(
            email=serializer.validated_data["email"]
        ).first()
        if not user:
            user = models.User(email=serializer.validated_data["email"])
            user.set_unusable_password()
            user.save()

        login(request, user, "django.contrib.auth.backends.ModelBackend")
        ensure_main_workspace(user)
        # Ensure the CSRF cookie is set for subsequent SPA mutations.
        # This endpoint is called via Playwright's APIRequestContext (not subject to CORS),
        # so setting the cookie here is the most reliable way to bootstrap the browser state.
        get_token(request)

        return drf_response.Response({"email": user.email}, status=status.HTTP_200_OK)


def _quote_ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


class ClearDbAPIView(APIView):
    """
    POST /api/v1.0/e2e/clear-db/
    Truncate application tables for E2E runs.

    Auth: Server-to-server bearer token (see SERVER_TO_SERVER_API_TOKENS).
    """

    permission_classes = [AllowAny]
    authentication_classes = [ServerToServerAuthentication]

    def post(self, request):
        """Truncate application tables for E2E runs."""
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
                stmt = (
                    "TRUNCATE TABLE "
                    + ", ".join(_quote_ident(t) for t in tables)
                    + " CASCADE"
                )
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
