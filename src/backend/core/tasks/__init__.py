"""Celery tasks for the core app.

Celery autodiscovery imports the `core.tasks` module. Import task modules here
to ensure they are registered when workers start.
"""

# pylint: disable=unused-import

from core.tasks import (  # noqa: F401
    archive,
    docs_documents,
    item,
    search,
    storage,
    storage_connections,
    user_reconciliation,
)
