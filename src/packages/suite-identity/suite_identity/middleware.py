"""Session revocation independent of the identity provider's logout capability."""

import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .access import (
    DirectoryUnavailable,
    enabled,
    remember_proof,
    request_accounts,
    request_proofs,
    require_access,
)
from .login import (
    AccessNotAssigned,
    AssociationPending,
    AuthenticationRequired,
    IdentityServiceUnavailable,
)


def remember_authentication(sender, request, user, **kwargs):
    """Save the validated proof after Django has rotated/flushed the session."""
    proof = getattr(request, "suite_authenticated", None)
    if proof:
        request.session["suite_identity"] = proof


class IdentitySessionMiddleware:
    """Protect existing browser sessions while leaving anonymous public flows intact."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .document_transport import document_links, validated_links

        token = request_accounts.set({})
        proof_token = request_proofs.set({})
        links_token = document_links.set(validated_links(request.session.get("document_links")))
        try:
            response = self.get_response(request)
            if enabled() and response.status_code < 400 and request.user.is_authenticated:
                account = request_accounts.get().get(request.user.pk)
                if account and account.checked_at and account.policy_checked_at:
                    deadline = min(account.checked_at, account.policy_checked_at) + timedelta(
                        seconds=settings.SUITE_IDENTITY_MAX_STALE_SECONDS
                    )
                    remaining = (deadline - timezone.now()).total_seconds()
                    proof = (request_proofs.get() or {}).get(
                        request.user.pk
                    ) or request.session.get("suite_identity", {})
                    if "auth_until" in proof:
                        remaining = min(remaining, proof["auth_until"] - time.time())
                    response["X-Suite-Access-TTL"] = str(max(0, int(remaining)))
                    response["Cache-Control"] = "private, no-store"
            return response
        finally:
            request_accounts.reset(token)
            request_proofs.reset(proof_token)
            document_links.reset(links_token)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Allow the OIDC recovery/logout flow itself to repair an expired session."""
        if request.resolver_match and (
            (request.resolver_match.url_name or "").startswith("oidc_")
            or request.resolver_match.url_name == "suite_logout"
        ):
            return None
        if enabled() and request.user.is_authenticated:
            backend = request.session.get("_auth_user_backend", "")
            # Local password authentication remains restricted to Django admin.
            # It is not an exception to API permissions, even for a superuser.
            admin_path = "/" + str(getattr(settings, "ADMIN_URL", "admin/")).lstrip("/")
            if backend == "django.contrib.auth.backends.ModelBackend" and request.path.startswith(
                admin_path
            ):
                return None
            try:
                account = require_access(request.user)
                proof = request.session.get("suite_identity", {})
                if (
                    proof.get("principal_id") != str(account.principal_id)
                    or proof.get("session_version") != account.session_version
                    or proof.get("issuer") != settings.SUITE_OIDC_ISSUER
                    or proof.get("auth_until", 0) <= time.time()
                ):
                    logout(request)
                    return JsonResponse(
                        {
                            "detail": "A new authentication is required",
                            "code": "suite_session_expired",
                        },
                        status=401,
                    )
                remember_proof(request.user, proof)
            except DirectoryUnavailable:
                return JsonResponse(
                    {
                        "detail": "Access verification temporarily unavailable",
                        "code": "suite_directory_unavailable",
                    },
                    status=503,
                )
            except PermissionDenied:
                return JsonResponse(
                    {"detail": "Access is not assigned", "code": "suite_access_denied"},
                    status=403,
                )
        return None

    def process_exception(self, request, exception):
        """Present actionable recovery without exposing tokens or external claims."""
        if (
            not enabled()
            or not request.resolver_match
            or not (request.resolver_match.url_name or "").startswith("oidc_")
        ):
            return None
        if isinstance(exception, AuthenticationRequired):
            title = "Nouvelle authentification nécessaire"
            detail = "Votre session de la suite a expiré ou a été révoquée. Identifiez-vous à nouveau auprès de votre fournisseur."
            action = "S’identifier à nouveau"
            url = reverse("oidc_authentication_init") + "?reauthenticate=1"
            status = 401
        elif isinstance(exception, AssociationPending):
            title = "Rattachement en attente"
            detail = "Votre connexion a été vérifiée. Un administrateur doit maintenant rattacher cette identité à votre compte dans People. Aucun accès n’est accordé avant sa validation."
            action, url, status = (
                "Réessayer après validation",
                reverse("oidc_authentication_init"),
                403,
            )
        elif isinstance(exception, (DirectoryUnavailable, IdentityServiceUnavailable)):
            title = "Vérification temporairement indisponible"
            detail = "Le service d’identité ou d’accès ne répond pas. Vos données sont conservées. Réessayez dans quelques instants."
            action, url, status = "Réessayer", reverse("oidc_authentication_init"), 503
        elif isinstance(exception, AccessNotAssigned):
            title = "Accès non attribué"
            detail = "Votre compte est reconnu, mais vous ne disposez pas d’un accès à cette application. Contactez votre administrateur."
            action, url, status = (
                "Réessayer après attribution",
                reverse("oidc_authentication_init"),
                403,
            )
        else:
            return None
        response = HttpResponse(
            format_html(
                '<!doctype html><html lang="fr"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                "<title>{}</title><body><main><h1>{}</h1><p>{}</p>"
                '<a href="{}">{}</a></main></body></html>',
                title,
                title,
                detail,
                url,
                action,
            ),
            status=status,
        )
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response
