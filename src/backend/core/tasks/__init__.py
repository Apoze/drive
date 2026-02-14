"""Celery tasks for the core app.

Celery autodiscovery imports the `core.tasks` module. Import task modules here
to ensure they are registered when workers start.
"""

# pylint: disable=unused-import

from core.tasks import archive, item, search, storage  # noqa: F401

