"""Explicit, repeatable association of an existing account; no email lookup."""

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from suite_identity.models import Account, IdentityBinding


class Command(BaseCommand):
    """Simulate by default; applying requires exact local and external identifiers."""

    help = "Associate an existing local user with a People principal and verified OIDC identity"

    def add_arguments(self, parser):
        parser.add_argument("--user-id", required=True)
        parser.add_argument("--principal-id", required=True, type=uuid.UUID)
        parser.add_argument("--organization-id", required=True, type=uuid.UUID)
        parser.add_argument("--issuer")
        parser.add_argument("--subject")
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            for field in ("principal_id", "organization_id"):
                options[field] = uuid.UUID(str(options[field]))
        except (TypeError, ValueError) as exc:
            raise CommandError("Valid principal and organization UUIDs required") from exc
        if bool(options["issuer"]) != bool(options["subject"]):
            raise CommandError("Provide both issuer and subject, or neither for an unbound account")
        try:
            user = get_user_model().objects.select_for_update().get(pk=options["user_id"])
        except (get_user_model().DoesNotExist, ValueError) as exc:
            raise CommandError("Existing local account required") from exc
        account = Account.objects.filter(user=user).first()
        if account and (
            account.principal_id != options["principal_id"]
            or account.organization_id != options["organization_id"]
        ):
            raise CommandError("Existing principal or organization association conflicts")
        if Account.objects.filter(principal_id=options["principal_id"]).exclude(user=user).exists():
            raise CommandError("Principal already belongs to a different local account")
        binding = (
            IdentityBinding.objects.filter(
                issuer=options["issuer"], subject=options["subject"]
            ).first()
            if options["issuer"]
            else None
        )
        if binding and binding.user_id != user.pk:
            raise CommandError("External identity already belongs to a different account")
        candidate = (
            binding
            or IdentityBinding(user=user, issuer=options["issuer"], subject=options["subject"])
            if options["issuer"]
            else None
        )
        if candidate:
            candidate.full_clean()
        if options["apply"]:
            Account.objects.get_or_create(
                user=user,
                defaults={
                    "principal_id": options["principal_id"],
                    "organization_id": options["organization_id"],
                },
            )
            if candidate and not binding:
                candidate.save()
        self.stdout.write(
            "Association applied" if options["apply"] else "Association valid; dry run, no changes"
        )
