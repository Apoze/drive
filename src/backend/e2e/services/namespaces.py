"""Deterministic namespace helpers for E2E bootstrap scopes."""

# pylint: disable=missing-function-docstring

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str, *, max_length: int) -> str:
    raw = str(value or "").strip().lower()
    normalized = _NON_ALNUM_RE.sub("-", raw).strip("-") or "scope"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    prefix_length = max(1, max_length - len(digest) - 1)
    prefix = normalized[:prefix_length].strip("-") or "scope"
    return f"{prefix}-{digest}"


def run_scope_slug(run_id: str) -> str:
    """Return the canonical slug for one Playwright run."""
    return _slugify(run_id, max_length=20)


def worker_scope_slug(worker_id: str) -> str:
    """Return the canonical slug for one Playwright worker."""
    return _slugify(worker_id, max_length=16)


@dataclass(frozen=True, slots=True)
class SessionNamespace:
    """Worker-scoped namespace for deterministic actors."""

    run_id: str
    worker_id: str
    actor_key: str

    @property
    def run_slug(self) -> str:
        return run_scope_slug(self.run_id)

    @property
    def worker_slug(self) -> str:
        return worker_scope_slug(self.worker_id)

    @property
    def actor_short_name_prefix(self) -> str:
        return f"e2e-{self.run_slug}-{self.worker_slug}"

    @property
    def actor_slug(self) -> str:
        return _slugify(
            f"{self.run_id}-{self.worker_id}-{self.actor_key}",
            max_length=32,
        )

    @property
    def actor_email(self) -> str:
        return f"e2e+{self.actor_slug}@example.com"

    @property
    def actor_full_name(self) -> str:
        actor_label = str(self.actor_key or "actor").replace("-", " ").strip().title()
        suffix = f"{self.run_slug} {self.worker_slug} {self.actor_slug}"
        available = 100 - len("E2E ") - len(suffix) - 1
        if available <= 0:
            return f"E2E {self.actor_slug}"[:100]
        compact_label = actor_label[:available].rstrip() or "Actor"
        return f"E2E {compact_label} {suffix}"

    @property
    def actor_short_name(self) -> str:
        return f"{self.actor_short_name_prefix}-{self.actor_key}"[:100]

    @property
    def storage_state_slug(self) -> str:
        return _slugify(
            f"{self.run_id}-{self.worker_id}-{self.actor_key}-storage-state",
            max_length=40,
        )

    @property
    def mount_run_path(self) -> str:
        return f"/e2e/{self.run_slug}"

    @property
    def mount_worker_path(self) -> str:
        return f"{self.mount_run_path}/{self.worker_slug}"

    @property
    def mount_actor_path(self) -> str:
        return f"{self.mount_worker_path}/{self.actor_slug}"

    def as_dict(self) -> dict[str, str]:
        """Return a stable JSON-serializable scope payload."""
        return {
            "run_id": self.run_id,
            "worker_id": self.worker_id,
            "actor_key": self.actor_key,
            "run_slug": self.run_slug,
            "worker_slug": self.worker_slug,
            "actor_slug": self.actor_slug,
            "actor_email": self.actor_email,
            "actor_full_name": self.actor_full_name,
            "actor_short_name": self.actor_short_name,
            "actor_short_name_prefix": self.actor_short_name_prefix,
            "storage_state_slug": self.storage_state_slug,
            "mount_run_path": self.mount_run_path,
            "mount_worker_path": self.mount_worker_path,
            "mount_actor_path": self.mount_actor_path,
        }

    def with_actor(self, actor_key: str) -> "SessionNamespace":
        """Return the same worker scope with a different actor key."""
        return SessionNamespace(
            run_id=self.run_id,
            worker_id=self.worker_id,
            actor_key=actor_key,
        )


@dataclass(frozen=True, slots=True)
class ScenarioNamespace(SessionNamespace):
    """Scenario-scoped namespace for deterministic E2E datasets."""

    scenario_id: str

    @property
    def scenario_slug(self) -> str:
        return _slugify(
            f"{self.run_id}-{self.worker_id}-{self.actor_key}-{self.scenario_id}",
            max_length=36,
        )

    @property
    def mount_root_path(self) -> str:
        return f"{self.mount_actor_path}/{self.scenario_slug}"

    @property
    def isolated_workspace_title(self) -> str:
        return self.folder_title("E2E workspace")

    @property
    def shared_workspace_title(self) -> str:
        return self.folder_title("E2E shared")

    @property
    def search_dataset_title(self) -> str:
        return self.folder_title("E2E search")

    @property
    def preview_fixture_title(self) -> str:
        return self.folder_title("E2E preview")

    @property
    def legacy_conversion_fixture_title(self) -> str:
        return self.folder_title("E2E legacy conversion")

    @property
    def scenario_folder_titles(self) -> dict[str, str]:
        return {
            "isolated_workspace_root": self.isolated_workspace_title,
            "paired_share": self.shared_workspace_title,
            "search_dataset": self.search_dataset_title,
            "preview_fixture_set": self.preview_fixture_title,
            "legacy_conversion_fixture": self.legacy_conversion_fixture_title,
        }

    def folder_title(self, prefix: str) -> str:
        """Return a deterministic folder title for a scenario root."""
        return f"{prefix} {self.scenario_slug}"

    def as_dict(self) -> dict[str, str]:
        """Return a stable JSON-serializable scenario payload."""
        payload = SessionNamespace.as_dict(self)
        payload.update(
            {
                "scenario_id": self.scenario_id,
                "scenario_slug": self.scenario_slug,
                "mount_root_path": self.mount_root_path,
                "isolated_workspace_title": self.isolated_workspace_title,
                "shared_workspace_title": self.shared_workspace_title,
                "search_dataset_title": self.search_dataset_title,
                "preview_fixture_title": self.preview_fixture_title,
                "legacy_conversion_fixture_title": self.legacy_conversion_fixture_title,
            }
        )
        return payload
