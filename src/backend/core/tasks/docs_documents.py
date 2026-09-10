"""Bounded retries of document metadata, using the existing Celery deployment."""

from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from rest_framework.exceptions import APIException

from core.models import DocsBinding, DocsInvitation
from core.services.docs_invitations import _mark_delivery, deliver
from core.services.docs_lifecycle import synchronize
from core.services.docs_resources import enabled

from drive.celery_app import app


@app.on_after_finalize.connect
def setup_document_reconciliation(sender, **kwargs):
    """The durable rows survive a worker restart or a lost broker message."""
    if enabled():
        sender.add_periodic_task(10, reconcile_documents.s(), name="docs_metadata_reconciliation")
        sender.add_periodic_task(
            30, deliver_document_invitations.s(), name="docs_invitation_delivery"
        )


@app.task
def reconcile_documents():
    """Dispatch a bounded pass; one unavailable document cannot monopolize a worker."""
    if not enabled():
        return
    ids = (
        DocsBinding.objects.exclude(state="purged")
        .filter(
            Q(retry_at__isnull=True) | Q(retry_at__lte=timezone.now()),
            applied_revision__lt=F("revision"),
        )
        .order_by("created_at", "pk")
        .values_list("pk", flat=True)[:50]
    )
    for binding_id in ids:
        synchronize_document.delay(str(binding_id))


@app.task
def synchronize_document(binding_id):
    """The peer revision and conditional acknowledgement make repeated delivery safe."""
    return synchronize(binding_id)


@app.task
def deliver_document_invitations():
    """Recover interrupted sending without silently duplicating an email."""
    if not enabled():
        return
    for state in DocsInvitation.objects.filter(
        context__delivery="sending",
        updated_at__lt=timezone.now() - timedelta(minutes=10),
    ).order_by("updated_at")[:50]:
        _mark_delivery(state, "uncertain")
    for state_id in (
        DocsInvitation.objects.filter(context__delivery="queued")
        .order_by("updated_at")
        .values_list("pk", flat=True)[:50]
    ):
        try:
            deliver(state_id)
        except APIException:
            # A stale directory or policy leaves the authorized invitation pending.
            pass
        DocsInvitation.objects.filter(pk=state_id, context__delivery="queued").update(
            updated_at=timezone.now()
        )
