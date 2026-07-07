"""E2E bootstrap contract services."""

from __future__ import annotations

from contextlib import suppress
from io import BytesIO

from django.conf import settings
from django.core.files.storage import default_storage

from lasuite.drf.models.choices import LinkReachChoices
from rest_framework import serializers

from core import models
from core.mounts.providers.base import MountProviderError
from core.mounts.registry import get_mount_provider

from e2e.services.namespaces import ScenarioNamespace, SessionNamespace
from e2e.utils import (
    DEFAULT_E2E_LANGUAGE,
    clear_workspace_descendants,
    delete_item_subtree,
    ensure_item_owner_access,
    ensure_main_workspace,
    ensure_named_child_folder,
    find_main_workspace,
    get_e2e_users_for_scope,
    get_or_create_e2e_user,
)

_MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<<>>endobj\n"
    b"2 0 obj<</Type/Catalog/Pages 3 0 R>>endobj\n"
    b"3 0 obj<</Type/Pages/Count 1/Kids[4 0 R]>>endobj\n"
    b"4 0 obj<</Type/Page/Parent 3 0 R/MediaBox[0 0 200 200]"
    b"/Contents 5 0 R/Resources<</Font<</F1 6 0 R>>>>>>endobj\n"
    b"5 0 obj<</Length 44>>stream\nBT /F1 18 Tf 36 110 Td (E2E PDF fixture) Tj ET\n"
    b"endstream endobj\n"
    b"6 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 7\n0000000000 65535 f \n0000000010 00000 n \n0000000031 00000 n \n"
    b"0000000080 00000 n \n0000000137 00000 n \n0000000261 00000 n \n"
    b"0000000356 00000 n \ntrailer<</Root 2 0 R/Size 7>>\nstartxref\n421\n%%EOF\n"
)
_HEIC_PLACEHOLDER_BYTES = b"ftypheic\x00\x00\x00\x00e2e-heic-placeholder"
_LEGACY_DOC_BYTES = (
    b"{\\rtf1\\ansi\\deff0"
    b"{\\fonttbl{\\f0 Arial;}}"
    b"\\f0\\fs24 E2E legacy Word fixture for conversion QA.\\par"
    b"}"
)


def _serialize_item(item: models.Item) -> dict[str, str | bool | None]:
    return {
        "id": str(item.id),
        "title": item.title,
        "type": item.type,
        "main_workspace": item.main_workspace,
        "deleted": item.deleted_at is not None,
    }


def _serialize_actor(user: models.User, *, created: bool) -> dict[str, str | bool | None]:
    return {
        "id": str(user.id),
        "email": user.email,
        "created": created,
        "full_name": user.full_name,
        "short_name": user.short_name,
        "language": user.language,
    }


def _serialize_mount_result(
    *,
    mount_id: str,
    root_path: str,
    created_paths: list[str],
    io: dict[str, bool],
) -> dict[str, object]:
    return {
        "mount_id": mount_id,
        "root_path": root_path,
        "created_paths": created_paths,
        "io": io,
    }


def _mount_io_capabilities(*, provider, mount: dict) -> dict[str, bool]:
    _ = mount
    return {
        "stat": hasattr(provider, "stat"),
        "open_read": hasattr(provider, "open_read"),
        "open_write": hasattr(provider, "open_write"),
        "rename": hasattr(provider, "rename"),
        "remove": hasattr(provider, "remove"),
        "mkdirs": hasattr(provider, "mkdirs"),
    }


def _enabled_mounts() -> list[dict]:
    mounts = list(getattr(settings, "MOUNTS_REGISTRY", []) or [])
    return [mount for mount in mounts if bool(mount.get("enabled", True))]


def _resolve_mount(mount_id: str | None) -> dict:
    mounts = _enabled_mounts()
    if not mounts:
        raise serializers.ValidationError({"mount_id": "No enabled mount is configured."})

    if mount_id:
        for mount in mounts:
            if mount.get("mount_id") == mount_id:
                return mount
        raise serializers.ValidationError({"mount_id": "Unknown mount."})

    return mounts[0]


def _cleanup_mounts(mount_id: str | None) -> list[dict]:
    if mount_id:
        return [_resolve_mount(mount_id)]
    return _enabled_mounts()


def _remove_mount_tree(  # noqa: PLR0912  # pylint: disable=too-many-branches
    *,
    provider,
    mount: dict,
    normalized_path: str,
) -> list[str]:
    removed_paths: list[str] = []
    if not hasattr(provider, "remove"):
        return removed_paths

    if hasattr(provider, "list_children"):
        try:
            children = provider.list_children(
                mount=mount,
                normalized_path=normalized_path,
            )
        except MountProviderError as exc:
            if exc.public_code == "mount.path.not_found":
                return removed_paths
            children = []

        for child in children:
            if child.entry_type == "folder":
                removed_paths.extend(
                    _remove_mount_tree(
                        provider=provider,
                        mount=mount,
                        normalized_path=child.normalized_path,
                    )
                )
            else:
                try:
                    provider.remove(
                        mount=mount,
                        normalized_path=child.normalized_path,
                    )
                except MountProviderError as exc:
                    if exc.public_code != "mount.path.not_found":
                        raise
                else:
                    removed_paths.append(child.normalized_path)

    try:
        provider.remove(mount=mount, normalized_path=normalized_path)
    except MountProviderError as exc:
        if exc.public_code != "mount.path.not_found":
            raise
    else:
        removed_paths.append(normalized_path)

    return removed_paths


def _ensure_ready_file(
    *,
    parent: models.Item,
    creator: models.User,
    title: str,
    content: bytes,
    mimetype: str,
) -> models.Item:
    item = (
        parent.children()
        .filter(title=title, type=models.ItemTypeChoices.FILE)
        .order_by("created_at")
        .first()
    )
    created = item is None
    if not item:
        item = models.Item.objects.create_child(
            parent=parent,
            creator=creator,
            link_reach=LinkReachChoices.RESTRICTED,
            type=models.ItemTypeChoices.FILE,
            title=title,
            filename=title,
            mimetype=mimetype,
            size=len(content),
            upload_state=models.ItemUploadStateChoices.READY,
        )
        item.upload_state = models.ItemUploadStateChoices.READY
        item.upload_started_at = None
        item.save(update_fields=["upload_state", "upload_started_at", "updated_at"])
    else:
        if item.deleted_at is not None:
            item.restore()
        item.filename = title
        item.mimetype = mimetype
        item.size = len(content)
        item.upload_state = models.ItemUploadStateChoices.READY
        item.upload_started_at = None
        item.save(
            update_fields=[
                "filename",
                "mimetype",
                "size",
                "upload_state",
                "upload_started_at",
                "updated_at",
            ]
        )

    ensure_item_owner_access(item, creator)

    with suppress(Exception):  # pylint: disable=broad-exception-caught
        if default_storage.exists(item.file_key):
            default_storage.delete(item.file_key)
    default_storage.save(item.file_key, BytesIO(content))

    if created:
        item.refresh_from_db()
    return item


def seed_search_dataset(*, parent: models.Item, creator: models.User) -> list[models.Item]:
    """Create or reuse the canonical E2E search tree under `parent`."""

    def _ensure_child(
        *,
        current_parent: models.Item,
        title: str,
        item_type: str,
        deleted: bool = False,
        children: list[dict] | None = None,
    ) -> models.Item:
        if item_type == models.ItemTypeChoices.FOLDER:
            item = ensure_named_child_folder(
                current_parent,
                title=title,
                creator=creator,
            )
        else:
            item = _ensure_ready_file(
                parent=current_parent,
                creator=creator,
                title=title,
                content=f"E2E search fixture: {title}\n".encode("utf-8"),
                mimetype="text/plain",
            )

        if deleted and item.deleted_at is None:
            item.soft_delete()
        if not deleted and item.deleted_at is not None:
            item.restore()

        for child in children or []:
            _ensure_child(current_parent=item, **child)
        return item

    content = [
        {
            "title": "Project 2025",
            "item_type": models.ItemTypeChoices.FOLDER,
            "children": [
                {
                    "title": "Budget report",
                    "item_type": models.ItemTypeChoices.FILE,
                },
                {
                    "title": "Sales report",
                    "item_type": models.ItemTypeChoices.FILE,
                },
                {
                    "title": "I am deleted",
                    "item_type": models.ItemTypeChoices.FOLDER,
                    "deleted": True,
                },
                {
                    "title": "Resume",
                    "item_type": models.ItemTypeChoices.FILE,
                    "deleted": True,
                },
            ],
        },
        {
            "title": "Dev Team",
            "item_type": models.ItemTypeChoices.FOLDER,
            "children": [
                {
                    "title": "Backlog",
                    "item_type": models.ItemTypeChoices.FILE,
                },
                {
                    "title": "Meetings",
                    "item_type": models.ItemTypeChoices.FOLDER,
                    "children": [
                        {
                            "title": "Meeting notes 5th September",
                            "item_type": models.ItemTypeChoices.FILE,
                        },
                        {
                            "title": "Meeting notes 15th September",
                            "item_type": models.ItemTypeChoices.FILE,
                        },
                    ],
                },
            ],
        },
    ]

    return [_ensure_child(current_parent=parent, **entry) for entry in content]


def seed_legacy_conversion_fixture(
    *,
    parent: models.Item,
    creator: models.User,
) -> models.Item:
    """Create or reuse the regular legacy Office fixture used by browser QA."""

    return _ensure_ready_file(
        parent=parent,
        creator=creator,
        title="legacy-conversion-fixture.doc",
        content=_LEGACY_DOC_BYTES,
        mimetype="application/msword",
    )


class E2EBootstrapService:
    """Create deterministic actors and scenario data without DB-global truncation."""

    def bootstrap_session(  # noqa: PLR0913  # pylint: disable=too-many-arguments
        self,
        *,
        run_id: str,
        worker_id: str,
        actor_key: str,
        email: str | None = None,
        language: str | None = DEFAULT_E2E_LANGUAGE,
        full_name: str | None = None,
        short_name: str | None = None,
    ) -> dict[str, object]:
        """Create or reuse one deterministic actor and main workspace scope."""
        namespace = SessionNamespace(
            run_id=run_id,
            worker_id=worker_id,
            actor_key=actor_key,
        )
        actor_email = email or namespace.actor_email
        created = not models.User.objects.filter(email=actor_email).exists()
        user = get_or_create_e2e_user(
            actor_email,
            full_name=full_name or namespace.actor_full_name,
            short_name=short_name or namespace.actor_short_name,
            language=language,
        )
        workspace = ensure_main_workspace(user)

        return {
            "namespace": namespace,
            "user": user,
            "workspace": workspace,
            "response": {
                "scope": namespace.as_dict(),
                "actor": _serialize_actor(user, created=created),
                "workspace": _serialize_item(workspace),
            },
        }

    def bootstrap_scenario(  # noqa: PLR0913  # pylint: disable=too-many-arguments,too-many-locals
        self,
        *,
        kind: str,
        run_id: str,
        worker_id: str,
        actor_key: str,
        scenario_id: str,
        secondary_actor_key: str = "secondary",
        mount_id: str | None = None,
    ) -> dict[str, object]:
        """Seed one deterministic scenario scope for Playwright fixtures."""
        namespace = ScenarioNamespace(
            run_id=run_id,
            worker_id=worker_id,
            actor_key=actor_key,
            scenario_id=scenario_id,
        )
        actor_ctx = self.bootstrap_session(
            run_id=run_id,
            worker_id=worker_id,
            actor_key=actor_key,
            language=DEFAULT_E2E_LANGUAGE,
        )
        user = actor_ctx["user"]
        workspace = actor_ctx["workspace"]

        if kind == "isolated_workspace_root":
            folder = ensure_named_child_folder(
                workspace,
                title=namespace.isolated_workspace_title,
                creator=user,
            )
            result = {"workspace_root": _serialize_item(folder)}
        elif kind == "paired_share":
            shared_root = ensure_named_child_folder(
                workspace,
                title=namespace.shared_workspace_title,
                creator=user,
            )
            secondary_namespace = namespace.with_actor(secondary_actor_key)
            secondary_ctx = self.bootstrap_session(
                run_id=run_id,
                worker_id=worker_id,
                actor_key=secondary_actor_key,
                language=DEFAULT_E2E_LANGUAGE,
            )
            secondary_user = secondary_ctx["user"]
            models.ItemAccess.objects.get_or_create(
                item=shared_root,
                user=secondary_user,
                defaults={"role": models.RoleChoices.READER},
            )
            result = {
                "shared_root": _serialize_item(shared_root),
                "secondary_actor": {
                    **secondary_namespace.as_dict(),
                    "id": str(secondary_user.id),
                    "email": secondary_user.email,
                },
            }
        elif kind == "search_dataset":
            dataset_root = ensure_named_child_folder(
                workspace,
                title=namespace.search_dataset_title,
                creator=user,
            )
            roots = seed_search_dataset(parent=dataset_root, creator=user)
            result = {
                "dataset_root": _serialize_item(dataset_root),
                "root_entries": [_serialize_item(item) for item in roots],
            }
        elif kind == "preview_fixture_set":
            preview_root = ensure_named_child_folder(
                workspace,
                title=namespace.preview_fixture_title,
                creator=user,
            )
            files = [
                _ensure_ready_file(
                    parent=preview_root,
                    creator=user,
                    title="fixture-preview.pdf",
                    content=_MINIMAL_PDF_BYTES,
                    mimetype="application/pdf",
                ),
                _ensure_ready_file(
                    parent=preview_root,
                    creator=user,
                    title="fixture-readme.txt",
                    content=b"E2E preview fixture\n",
                    mimetype="text/plain",
                ),
                _ensure_ready_file(
                    parent=preview_root,
                    creator=user,
                    title="fixture-heic.heic",
                    content=_HEIC_PLACEHOLDER_BYTES,
                    mimetype="image/heic",
                ),
            ]
            result = {
                "preview_root": _serialize_item(preview_root),
                "files": [_serialize_item(item) for item in files],
            }
        elif kind == "legacy_conversion_fixture":
            conversion_root = ensure_named_child_folder(
                workspace,
                title=namespace.legacy_conversion_fixture_title,
                creator=user,
            )
            legacy_file = seed_legacy_conversion_fixture(
                parent=conversion_root,
                creator=user,
            )
            result = {
                "conversion_root": _serialize_item(conversion_root),
                "legacy_file": {
                    **_serialize_item(legacy_file),
                    "filename": legacy_file.filename,
                    "mimetype": legacy_file.mimetype,
                    "upload_state": legacy_file.upload_state,
                    "abilities": {
                        "convert": bool(legacy_file.get_abilities(user).get("convert")),
                    },
                },
            }
        elif kind == "mount_subtree":
            mount = _resolve_mount(mount_id)
            provider = get_mount_provider(str(mount.get("provider") or ""))
            io = _mount_io_capabilities(provider=provider, mount=mount)
            if not io["mkdirs"]:
                raise serializers.ValidationError(
                    {"mount_id": "Mount scenario requires directory creation support."}
                )

            root_path = namespace.mount_root_path
            created_paths = [
                root_path,
                f"{root_path}/inbox",
                f"{root_path}/outbox",
            ]
            try:
                provider.mkdirs(mount=mount, normalized_path=root_path)
                provider.mkdirs(mount=mount, normalized_path=f"{root_path}/inbox")
                provider.mkdirs(mount=mount, normalized_path=f"{root_path}/outbox")
                if io["open_write"]:
                    with provider.open_write(
                        mount=mount,
                        normalized_path=f"{root_path}/README.txt",
                    ) as handle:
                        handle.write(
                            (f"E2E mount subtree for {namespace.scenario_slug}\n").encode("utf-8")
                        )
                    created_paths.append(f"{root_path}/README.txt")
            except MountProviderError as exc:
                raise serializers.ValidationError({"mount_id": exc.public_message}) from exc

            result = _serialize_mount_result(
                mount_id=str(mount.get("mount_id") or ""),
                root_path=root_path,
                created_paths=created_paths,
                io=io,
            )
        else:
            raise serializers.ValidationError({"kind": "Unsupported scenario kind."})

        return {
            "scope": namespace.as_dict(),
            "kind": kind,
            "actor": {
                "id": str(user.id),
                "email": user.email,
            },
            "result": result,
        }

    def cleanup_scope(  # pylint: disable=too-many-arguments
        self,
        *,
        run_id: str,
        worker_id: str | None = None,
        actor_key: str | None = None,
        scenario_id: str | None = None,
        mount_id: str | None = None,
    ) -> dict[str, object]:
        """Delete one E2E namespace without falling back to DB-global truncation."""
        if scenario_id is not None:
            return self._cleanup_scenario(
                run_id=run_id,
                worker_id=str(worker_id),
                actor_key=str(actor_key),
                scenario_id=scenario_id,
                mount_id=mount_id,
            )

        return self._cleanup_session_scope(
            run_id=run_id,
            worker_id=worker_id,
            actor_key=actor_key,
            mount_id=mount_id,
        )

    def _cleanup_scenario(  # pylint: disable=too-many-arguments
        self,
        *,
        run_id: str,
        worker_id: str,
        actor_key: str,
        scenario_id: str,
        mount_id: str | None,
    ) -> dict[str, object]:
        """Delete one scenario namespace and its optional mount subtree only."""
        namespace = ScenarioNamespace(
            run_id=run_id,
            worker_id=worker_id,
            actor_key=actor_key,
            scenario_id=scenario_id,
        )
        deleted_titles: list[str] = []
        deleted_item_count = 0
        actor_found = False

        user = models.User.objects.filter(email=namespace.actor_email).first()
        if user:
            actor_found = True
            workspace = find_main_workspace(user)
            if workspace:
                for title in namespace.scenario_folder_titles.values():
                    root = (
                        workspace.children()
                        .filter(
                            title=title,
                            type=models.ItemTypeChoices.FOLDER,
                            hard_deleted_at__isnull=True,
                        )
                        .order_by("created_at")
                        .first()
                    )
                    if not root:
                        continue
                    deleted_item_count += delete_item_subtree(root)
                    deleted_titles.append(title)

        deleted_mount_paths: list[str] = []
        for mount in _cleanup_mounts(mount_id):
            provider = get_mount_provider(str(mount.get("provider") or ""))
            deleted_mount_paths.extend(
                _remove_mount_tree(
                    provider=provider,
                    mount=mount,
                    normalized_path=namespace.mount_root_path,
                )
            )

        return {
            "scope": namespace.as_dict(),
            "cleanup": {
                "mode": "scenario",
                "actor_found": actor_found,
                "deleted_titles": deleted_titles,
                "deleted_item_count": deleted_item_count,
                "deleted_mount_paths": deleted_mount_paths,
            },
        }

    def _cleanup_session_scope(
        self,
        *,
        run_id: str,
        worker_id: str | None,
        actor_key: str | None,
        mount_id: str | None,
    ) -> dict[str, object]:
        mode = "run"
        scope: dict[str, object] = {
            "run_id": run_id,
            "run_slug": SessionNamespace(
                run_id=run_id,
                worker_id=worker_id or "worker",
                actor_key=actor_key or "actor",
            ).run_slug,
        }
        mount_root_path = f"/e2e/{scope['run_slug']}"

        if worker_id is not None:
            mode = "worker"
            scope["worker_id"] = worker_id
            scope["worker_slug"] = SessionNamespace(
                run_id=run_id,
                worker_id=worker_id,
                actor_key=actor_key or "actor",
            ).worker_slug
            mount_root_path = f"{mount_root_path}/{scope['worker_slug']}"

        if actor_key is not None:
            mode = "actor"
            namespace = SessionNamespace(
                run_id=run_id,
                worker_id=str(worker_id),
                actor_key=actor_key,
            )
            scope.update(namespace.as_dict())
            mount_root_path = namespace.mount_actor_path

        scope["mount_cleanup_path"] = mount_root_path

        deleted_item_count = 0
        matched_users: list[str] = []
        for user in get_e2e_users_for_scope(
            run_id=run_id,
            worker_id=worker_id,
            actor_key=actor_key,
        ):
            matched_users.append(user.email)
            workspace = find_main_workspace(user)
            if not workspace:
                continue
            deleted_item_count += clear_workspace_descendants(workspace)

        deleted_mount_paths: list[str] = []
        for mount in _cleanup_mounts(mount_id):
            provider = get_mount_provider(str(mount.get("provider") or ""))
            deleted_mount_paths.extend(
                _remove_mount_tree(
                    provider=provider,
                    mount=mount,
                    normalized_path=mount_root_path,
                )
            )

        return {
            "scope": scope,
            "cleanup": {
                "mode": mode,
                "matched_user_emails": matched_users,
                "deleted_item_count": deleted_item_count,
                "deleted_mount_paths": deleted_mount_paths,
            },
        }
