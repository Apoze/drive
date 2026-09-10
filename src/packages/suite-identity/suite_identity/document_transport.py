"""Narrow private document exchanges, using existing suite proofs and HTTP limits."""

import json
import hashlib
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from tempfile import SpooledTemporaryFile
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied

from .access import enabled, remember_proof, request_proofs, require_access, validate_delegation
from .http import open_response, read_credential, read_json
from .models import Account

MAX_MESSAGE_BYTES = 1024 * 1024
document_links = ContextVar("document_links", default=None)


def validated_links(value):
    """Bound bearer contexts; the storage authority still validates every grant."""
    from uuid import UUID

    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 8:
        raise AuthenticationFailed("Invalid document link context.")
    normalized = {}
    for key, link in value.items():
        try:
            identifier = str(UUID(key))
        except (ValueError, TypeError, AttributeError):
            raise AuthenticationFailed("Invalid document link context.") from None
        if (not isinstance(link, dict) or set(link) != {"kind", "token"}
                or link["kind"] not in {"item", "mount"}
                or not isinstance(link["token"], str)
                or not 1 <= len(link["token"]) <= 4096):
            raise AuthenticationFailed("Invalid document link context.")
        normalized[identifier] = link
    return normalized


@contextmanager
def pdf_stream(payload, *, actor, limit=128 * 1024**2):
    """Receive one bounded, verified PDF without exposing native storage credentials."""
    raw = json.dumps({"actor": actor, "payload": payload}, allow_nan=False).encode()
    if len(raw) > MAX_MESSAGE_BYTES:
        raise PermissionDenied("Document message is too large.")
    with SpooledTemporaryFile(max_size=8 * 1024**2) as spool:
        try:
            key = read_credential(settings.DOCUMENT_OUTBOUND_READ_KEY_FILE)
            with open_response(
                settings.DOCUMENT_PEER_API_URL.rstrip("/") + "/api/v1.0/internal/drive/pdf/",
                headers={"Content-Type": "application/json", "X-Document-Key": key},
                data=raw, timeout=140,
            ) as response:
                expected = int(response.headers.get("Content-Length", "0"))
                digest, size = hashlib.sha256(), 0
                if not 5 <= expected <= limit or response.headers.get_content_type() != "application/pdf":
                    raise ValueError("Invalid PDF response.")
                while chunk := response.read(min(1024 * 1024, limit - size + 1)):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("PDF exceeds its limit.")
                    digest.update(chunk)
                    spool.write(chunk)
                if size != expected or digest.hexdigest() != response.headers.get("X-Content-SHA256"):
                    raise ValueError("Incomplete PDF response.")
            spool.seek(0)
            if spool.read(5) != b"%PDF-":
                raise ValueError("Invalid PDF response.")
            spool.seek(0)
        except HTTPError as error:
            failure = APIException("Document export was refused.")
            failure.status_code = error.code if error.code in {401, 403, 404, 409, 413, 429} else 503
            raise failure from None
        except (URLError, OSError, ValueError, AttributeError):
            raise DocumentServiceUnavailable() from None
        yield spool


class DocumentServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Document service is temporarily unavailable."
    default_code = "document_service_unavailable"


def actor_context(user):
    """Delegation requires a real verified request; never synthesize a human session."""
    links = validated_links(document_links.get())
    if not user.is_authenticated:
        return {"links": links} if links else None
    account = require_access(user)
    proof = (request_proofs.get() or {}).get(user.pk)
    if account is None or not proof:
        raise PermissionDenied("A verified suite session is required.")
    validate_delegation(user, proof)
    return {"principal": str(account.principal_id),
            "organization": str(account.organization_id), "proof": dict(proof),
            **({"links": links} if links else {})}


def resolve_actor(context):
    """A trusted caller identifies a principal, not an application subject or email."""
    if not enabled():
        raise DocumentServiceUnavailable()
    links = validated_links(context.get("links") if isinstance(context, dict) else None)
    document_links.set(links)
    if context is None or isinstance(context, dict) and set(context) == {"links"}:
        return AnonymousUser()
    if not isinstance(context, dict) or not isinstance(context.get("proof"), dict):
        raise AuthenticationFailed("Invalid document actor.")
    from uuid import UUID
    from .directory import SnapshotError, synchronize

    try:
        principal = UUID(context["principal"])
        organization = UUID(context["organization"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise AuthenticationFailed("Invalid document actor.") from None
    if str(organization) != str(settings.SUITE_ORGANIZATION_ID):
        raise AuthenticationFailed("Document organization is not assigned.")
    associations = Account.objects.select_related("user").filter(
        principal_id=principal, organization_id=organization,
    )
    account = associations.first()
    if account is None:
        # First use in a peer may precede its periodic People projection. Only
        # the authoritative directory provisions accounts; the caller cannot.
        try:
            synchronize()
        except SnapshotError:
            raise DocumentServiceUnavailable() from None
        account = associations.first()
    if account is None:
        raise AuthenticationFailed("Document actor is not associated.")
    validate_delegation(account.user, context["proof"])
    remember_proof(account.user, context["proof"])
    return account.user


def receive(request, *, purpose, streaming=False):
    """Verify a route-specific key before parsing a bounded JSON message."""
    if purpose not in {"read", "mutation"}:
        raise ValueError("Invalid document credential purpose")
    try:
        expected = read_credential(getattr(settings, f"DOCUMENT_INBOUND_{purpose.upper()}_KEY_FILE"))
    except (OSError, ValueError, AttributeError):
        raise DocumentServiceUnavailable() from None
    supplied = request.headers.get("X-Document-Key", "")
    if (not supplied.isascii() or len(supplied) > 256
            or not secrets.compare_digest(supplied, expected)):
        raise AuthenticationFailed("Invalid document service credentials.")
    if request.content_type != ("application/pdf" if streaming else "application/json"):
        raise AuthenticationFailed("A JSON document message is required.")
    raw = (request.headers.get("X-Document-Context", "") if streaming
           else request.stream.read(MAX_MESSAGE_BYTES + 1))
    if len(raw) > (16384 if streaming else MAX_MESSAGE_BYTES):
        raise PermissionDenied("Document message is too large.")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AuthenticationFailed("Invalid document message.") from None
    if not isinstance(body, dict) or not isinstance(body.get("payload"), dict):
        raise AuthenticationFailed("Invalid document message.")
    request.user = resolve_actor(body.get("actor"))
    return body["payload"]


def send_file(path, payload, stream, *, size, actor):
    """Stream one bounded PDF to the configured peer with the mutation credential."""
    if path != "/api/v1.0/internal/docs/export/" or not 0 < size <= 128 * 1024 * 1024:
        raise PermissionDenied("Invalid document export.")
    context = json.dumps({"actor": actor, "payload": payload}, separators=(",", ":"))
    if len(context) > 16384:
        raise PermissionDenied("Document context is too large.")
    try:
        key = read_credential(settings.DOCUMENT_OUTBOUND_MUTATION_KEY_FILE)
        return read_json(
            settings.DOCUMENT_PEER_API_URL.rstrip("/") + path,
            headers={"Content-Type": "application/pdf", "Content-Length": str(size),
                     "X-Document-Key": key, "X-Document-Context": context},
            data=iter(lambda: stream.read(1024 * 1024), b""),
            limit=MAX_MESSAGE_BYTES, timeout=60,
        )
    except HTTPError as error:
        failure = APIException("Document export was refused. Retry with the same operation.")
        failure.status_code = error.code if error.code in {401, 403, 404, 409, 413, 429} else 503
        raise failure from None
    except (URLError, OSError, ValueError, AttributeError):
        raise DocumentServiceUnavailable() from None


def send(path, payload, *, purpose, actor=None):
    """Send only to the configured peer; never follow redirects or forward IdP tokens."""
    if purpose not in {"read", "mutation"} or not path.startswith("/") or ".." in path:
        raise ValueError("Invalid document service operation")
    raw = json.dumps(
        {"actor": actor, "payload": payload}, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(raw) > MAX_MESSAGE_BYTES:
        raise PermissionDenied("Document message is too large.")
    try:
        key = read_credential(getattr(settings, f"DOCUMENT_OUTBOUND_{purpose.upper()}_KEY_FILE"))
        return read_json(
            settings.DOCUMENT_PEER_API_URL.rstrip("/") + path,
            headers={"Content-Type": "application/json", "X-Document-Key": key},
            data=raw, limit=MAX_MESSAGE_BYTES,
        )
    except HTTPError as error:
        if error.code in {400, 401, 403, 404, 409, 413, 429}:
            failure = APIException("Document operation was refused.")
            failure.status_code = error.code
            raise failure from None
        raise DocumentServiceUnavailable() from None
    except (URLError, OSError, ValueError, AttributeError):
        raise DocumentServiceUnavailable() from None
