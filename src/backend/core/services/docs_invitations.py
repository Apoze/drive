"""One invitation authority and explicit, principal-bound acceptance for Docs."""

from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from suite_identity.access import request_proofs, require_access
from suite_identity.models import Account

from core.models import DocsInvitation, Invitation, Item, ItemAccess
from core.services.docs_resources import enabled
from core.services.item_activity import record_item_activity
from core.services.storage_namespace import advisory_guard

SALT = "drive.docs.invitation.v1"


def recipient_email(user):
    """The peer's verified login address takes precedence over a stale local profile."""
    email = ((request_proofs.get() or {}).get(user.pk) or {}).get("verified_email")
    if not isinstance(email, str) or not email or len(email) > 254:
        raise PermissionDenied("Sign in with an email address verified by your identity provider.")
    return email.casefold()


def change(item, actor, data):  # noqa: PLR0912
    """The lifecycle caller holds the item lock and journals the command once."""
    if not enabled() or not item.get_abilities(actor).get("accesses_manage"):
        raise PermissionDenied()
    action = data["action"]
    role = data.get("role")
    old_role = None
    if role == "owner" and item.get_role(actor) != "owner":
        raise PermissionDenied("Only an owner can invite another owner.")
    if action == "invite":
        invitation = Invitation.objects.filter(item=item, email__iexact=data["email"]).first()
        if invitation is None:
            invitation = Invitation.objects.create(
                item=item,
                issuer=actor,
                email=data["email"].casefold(),
                role=role,
            )
        context = {
            "status": "pending",
            "nonce": str(uuid4()),
            "delivery": "queued",
            "expires": int(
                (
                    invitation.created_at + timedelta(seconds=settings.INVITATION_VALIDITY_DURATION)
                ).timestamp()
            ),
        }
        state, created = DocsInvitation.objects.get_or_create(
            invitation=invitation,
            defaults={"context": context},
        )
        if not created and state.context.get("status") == "pending":
            if invitation.role != role:
                raise ValidationError("Update the existing invitation to change its role.")
            return invitation
        if not created:
            invitation.role = role
            invitation.issuer = actor
            invitation.save(update_fields=["role", "issuer", "updated_at"])
            context["expires"] = (
                int(timezone.now().timestamp()) + settings.INVITATION_VALIDITY_DURATION
            )
            state.context = context
    else:
        invitation = Invitation.objects.filter(pk=data["invitation_id"], item=item).first()
        if invitation is None:
            raise NotFound()
        old_role = invitation.role
        state = DocsInvitation.objects.select_for_update().filter(invitation=invitation).first()
        if state is None or state.context.get("status") != "pending":
            raise ValidationError("This invitation is no longer pending.")
        if action == "update_invitation" and invitation.role == role:
            return invitation
        if action == "revoke_invitation":
            state.context.update(status="revoked", delivery="cancelled", nonce=str(uuid4()))
        elif action in {"update_invitation", "resend_invitation"}:
            invitation.role = role or invitation.role
            invitation.issuer = actor
            invitation.save(update_fields=["role", "issuer", "updated_at"])
            state.context.update(
                nonce=str(uuid4()),
                delivery="queued",
                expires=int(
                    (
                        timezone.now() + timedelta(seconds=settings.INVITATION_VALIDITY_DURATION)
                    ).timestamp()
                ),
            )
        else:
            raise ValidationError("Unknown invitation operation.")
    state.save(update_fields=["context", "updated_at"])
    record_item_activity(
        item=item,
        actor=actor,
        action="invitation_revoked"
        if action == "revoke_invitation"
        else "invitation_created"
        if action == "invite"
        else "invitation_updated",
        payload={
            "target_name": invitation.email,
            **(
                {"old_role": old_role, "new_role": invitation.role}
                if action in {"update_invitation", "resend_invitation"}
                else {"role": invitation.role}
            ),
        },
    )
    return invitation


def page(item, user, query):
    """Read pending invitations only after checking current management rights."""
    if not enabled() or not item.get_abilities(user).get("accesses_manage"):
        raise PermissionDenied()
    rows = Invitation.objects.filter(item=item, docs_state__context__status="pending")
    if query.get("invitation_id"):
        rows = rows.filter(pk=query["invitation_id"])
    if query.get("email"):
        rows = rows.filter(email__iexact=query["email"])
    offset, limit = query.get("offset", 0), query.get("limit", 50)
    count = rows.count()
    result = []
    invitations = list(
        rows.select_related("docs_state").order_by("created_at", "pk")[offset : offset + limit]
    )
    issuers = dict(
        Account.objects.filter(user_id__in=[row.issuer_id for row in invitations]).values_list(
            "user_id", "principal_id"
        )
    )
    for invitation in invitations:
        invitation.item = item
        context = invitation.docs_state.context
        result.append(
            {
                "id": str(invitation.pk),
                "email": invitation.email,
                "role": invitation.role,
                "created_at": invitation.created_at,
                "is_expired": expired(context),
                "delivery_state": context.get("delivery", "queued"),
                "issuer_principal_id": str(issuers[invitation.issuer_id])
                if invitation.issuer_id in issuers
                else None,
                "abilities": invitation.get_abilities(user),
            }
        )
    return {"count": count, "results": result}


def expired(context):
    """Missing expiry never revives a partially migrated invitation."""
    return context.get("expires", 0) <= timezone.now().timestamp()


def acceptance_token(state):
    """A random row ID alone is never sufficient to accept an invitation."""
    return signing.Signer(salt=SALT).sign_object(
        {
            "id": str(state.invitation_id),
            "nonce": state.context["nonce"],
        }
    )


def accept(user, token):
    """Possession, matching recipient and a current suite proof bind the new grant."""
    if not enabled():
        raise NotFound()
    from suite_identity.document_transport import actor_context  # noqa: PLC0415

    actor = actor_context(user)
    if actor is None:
        raise PermissionDenied()
    email = recipient_email(user)
    try:
        payload = signing.Signer(salt=SALT).unsign_object(token)
        invitation = Invitation.objects.select_related("item").get(
            pk=payload["id"], item__type="docs"
        )
    except (
        signing.BadSignature,
        DjangoValidationError,
        ValueError,
        TypeError,
        KeyError,
        Invitation.DoesNotExist,
    ):
        raise PermissionDenied("Invalid document invitation.") from None
    # Resolve any NAS observation before the invitation/ACL transaction.
    from core.services.docs_resources import placement_capabilities  # noqa: PLC0415

    placement_capabilities(invitation.item, user)
    with transaction.atomic():
        item = Item.objects.select_for_update().get(pk=invitation.item_id)
        invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
        state = DocsInvitation.objects.select_for_update().filter(invitation=invitation).first()
        if (
            state is None
            or payload.get("nonce") != state.context.get("nonce")
            or invitation.email.casefold() != email
        ):
            raise PermissionDenied("Invalid document invitation.")
        if state.context.get("accepted_by") == actor["principal"]:
            return {"state": "accepted", "document_id": str(item.docs_binding.document_id)}
        if state.context.get("status") != "pending" or expired(state.context):
            raise PermissionDenied("The document invitation has expired or was revoked.")
        issuer = invitation.issuer
        if (
            issuer is None
            or not item.get_abilities(issuer).get("accesses_manage")
            or (invitation.role == "owner" and item.get_role(issuer) != "owner")
        ):
            raise PermissionDenied("The issuer can no longer grant this access.")
        existing = ItemAccess.objects.filter(item=item, user=user).first()
        role = item.access_role_choices.max(existing.role if existing else None, invitation.role)
        ItemAccess.objects.update_or_create(item=item, user=user, defaults={"role": role})
        state.context.update(
            status="accepted", accepted_by=actor["principal"], delivery="cancelled"
        )
        state.save(update_fields=["context", "updated_at"])
        record_item_activity(
            item=item,
            actor=user,
            action="user_access_created",
            payload={"target_name": user.full_name or user.email, "role": role},
        )
    return {"state": "accepted", "document_id": str(item.docs_binding.document_id)}


def deliver(state_id):
    """Keep an uncertain SMTP delivery explicit instead of automatically sending twice."""
    if not enabled():
        return
    with advisory_guard(f"docs-invitation-mail:{state_id}"):
        state = (
            DocsInvitation.objects.select_related("invitation__item", "invitation__issuer")
            .filter(pk=state_id)
            .first()
        )
        if state is None or state.context.get("delivery") != "queued":
            return
        invitation = state.invitation
        if state.context.get("status") != "pending" or expired(state.context):
            _mark_delivery(state, "cancelled")
            return
        if invitation.issuer is None or not settings.EMAIL_HOST or not settings.DOCS_PUBLIC_URL:
            return
        require_access(invitation.issuer)
        if not invitation.item.get_abilities(invitation.issuer).get("accesses_manage"):
            return
        with override(invitation.issuer.language or settings.LANGUAGE_CODE):
            context = {
                "brandname": settings.EMAIL_BRAND_NAME,
                "item": invitation.item,
                "domain": settings.DOCS_PUBLIC_URL,
                "logo_img": settings.EMAIL_LOGO_IMG,
                "title": _("Invitation to a document"),
                "message": _("Accept this invitation with your suite account."),
                "link": f"{settings.DOCS_PUBLIC_URL.rstrip('/')}/invitations/#token={acceptance_token(state)}",
            }
            message = EmailMultiAlternatives(
                _("Invitation to a document"),
                render_to_string("mail/text/invitation.txt", context),
                settings.EMAIL_FROM,
                [invitation.email],
                headers={
                    "Message-ID": f"<docs-invitation-{state.pk}-{state.context['nonce']}@drive.local>"
                },
                connection=get_connection(timeout=5),
            )
            message.attach_alternative(
                render_to_string("mail/html/invitation.html", context), "text/html"
            )
        if not _mark_delivery(state, "sending"):
            return
        try:
            delivered = message.send(fail_silently=False) == 1
        except (OSError, ValueError):
            delivered = False
        _mark_delivery(state, "sent" if delivered else "uncertain")


def _mark_delivery(state, delivery):
    """An email acknowledgement must never undo a concurrent acceptance or revocation."""
    context = {**state.context, "delivery": delivery}
    updated = DocsInvitation.objects.filter(pk=state.pk, context=state.context).update(
        context=context,
        updated_at=timezone.now(),
    )
    if updated:
        state.context = context
    return bool(updated)


def legacy_offer(user, document_id):
    """Old native emails name a document; only its authenticated recipient sees an offer."""
    if not enabled() or not user.is_authenticated:
        raise PermissionDenied()
    require_access(user)
    email = recipient_email(user)
    state = (
        DocsInvitation.objects.select_related("invitation__item")
        .filter(
            invitation__email__iexact=email,
            invitation__item__docs_binding__document_id=document_id,
            invitation__item__docs_binding__state="active",
            invitation__item__ancestors_deleted_at__isnull=True,
            context__status="pending",
            context__has_key="legacy_native_id",
        )
        .first()
    )
    if state is None or expired(state.context):
        return {"token": None}
    return {"token": acceptance_token(state)}
