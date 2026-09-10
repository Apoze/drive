"""Run shared reconciliation on an application's native Celery worker."""

from celery import shared_task

from .reconciliation import synchronize_identity as reconcile


@shared_task(name="suite_identity.synchronize", ignore_result=True)
def synchronize_identity():
    """Delegate to the same synchronous reconciliation as other schedulers."""
    return reconcile()
