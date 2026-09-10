"""Shared authenticated catalogue and suite logout, hosted by each application."""

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from uuid import UUID, uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.middleware.csrf import get_token

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import DirectoryUnavailable, enabled, request_proofs, require_access
from .directory import SnapshotError
from .http import read_credential, read_json
from .models import Account
from .policy import fetch_policy


class CatalogueView(APIView):
    """The menu is informative; each application still enforces its own access."""

    permission_classes = (AllowAny,)

    def get(self, request):
        get_token(request)
        if not enabled():
            return Response({"enabled": False, "services": []})
        if not request.user.is_authenticated:
            return Response({"enabled": True, "services": []}, status=401)
        try:
            account = require_access(request.user)
            result = fetch_policy(
                [str(account.principal_id)], endpoint=settings.SUITE_CATALOGUE_URL
            )
            if (
                result.get("version") != 1
                or result.get("principal_id") != str(account.principal_id)
                or result.get("organization_id") != str(account.organization_id)
                or result.get("service_id") != str(settings.SUITE_POLICY_SERVICE_ID)
                or not isinstance(result.get("services"), list)
                or len(result["services"]) > 100
            ):
                raise SnapshotError("invalid_catalogue")
            for service in result["services"]:
                url = urlsplit(service["url"])
                if (
                    url.scheme not in {"http", "https"}
                    or not url.hostname
                    or url.username
                    or url.password
                    or type(service["allowed"]) is not bool
                ):
                    raise SnapshotError("invalid_catalogue")
        except (
            DirectoryUnavailable,
            SnapshotError,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            return Response({"code": "suite_catalogue_unavailable"}, status=503)
        except PermissionDenied:
            return Response({"code": "suite_access_denied"}, status=403)
        return Response(
            {"enabled": True, "services": result["services"]},
            headers={"Cache-Control": "private, no-store"},
        )


class LogoutView(APIView):
    """CSRF-protected self-revocation; callers cannot supply another principal."""

    permission_classes = (AllowAny,)

    def get(self, request):
        get_token(request)
        return Response({"enabled": enabled()}, headers={"Cache-Control": "no-store"})

    def post(self, request):
        redirect = f"/api/{settings.API_VERSION}/logout/"
        if not enabled():
            return Response({"redirect_url": request.build_absolute_uri(redirect)})
        if not request.user.is_authenticated:
            return Response({"redirect_url": request.build_absolute_uri(redirect)})
        try:
            operation = str(
                UUID(
                    request.data.get("operation_id")
                    or request.session.get("suite_logout_operation")
                    or str(uuid4())
                )
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            return Response({"code": "invalid_operation"}, status=400)
        request.session["suite_logout_operation"] = operation
        request.session.save()
        try:
            # Ending one's own session remains possible after access is withdrawn.
            account = Account.objects.get(user_id=request.user.pk)
            proof = (request_proofs.get() or {}).get(request.user.pk) or request.session.get(
                "suite_identity", {}
            )
            if proof.get("principal_id") != str(account.principal_id):
                return Response({"redirect_url": request.build_absolute_uri(redirect)})
            token = read_credential(settings.SUITE_LOGOUT_TOKEN_FILE)
            result = read_json(
                settings.SUITE_LOGOUT_URL,
                data=urlencode(
                    {
                        "principal_id": str(account.principal_id),
                        "operation_id": operation,
                    }
                ).encode(),
                headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                limit=4096,
            )
            if (
                result.get("principal_id") != str(account.principal_id)
                or result.get("operation_id") != operation
                or type(result.get("session_version")) is not int
                or result["session_version"] < 1
            ):
                raise ValueError
        except (
            Account.DoesNotExist,
            DirectoryUnavailable,
            HTTPError,
            URLError,
            OSError,
            ValueError,
            AttributeError,
        ):
            return Response(
                {
                    "code": "suite_logout_unavailable",
                    "detail": "Déconnexion de la suite non confirmée. Réessayer.",
                },
                status=503,
            )
        # Native OIDC logout retains its state/id_token until the provider callback.
        # The People epoch independently invalidates all application sessions.
        return Response(
            {
                "redirect_url": request.build_absolute_uri(redirect),
                "suite_revoked": True,
                "provider_logout_available": bool(
                    getattr(settings, "OIDC_OP_LOGOUT_ENDPOINT", None)
                ),
            },
            headers={"Cache-Control": "private, no-store"},
        )
