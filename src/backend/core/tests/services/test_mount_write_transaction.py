"""Tests for MountProvider temp-write/final-rename mechanics."""

# pylint: disable=missing-function-docstring

from __future__ import annotations

import contextlib
import io

import pytest

from core.mounts.providers.base import MountProviderError
from core.services.mount_write_transaction import (
    MountWriteLimits,
    MountWriteTooLarge,
    copy_mount_file_transaction,
    write_mount_stream_transaction,
)


def _not_found() -> MountProviderError:
    return MountProviderError(
        failure_class="mount.path.not_found",
        next_action_hint="Verify the path exists in the mount and retry.",
        public_message="Mount path not found.",
        public_code="mount.path.not_found",
    )


class _MemoryMountProvider:
    def __init__(self, *, files: dict[str, bytes] | None = None, fail_rename: bool = False):
        self.files = dict(files or {})
        self.fail_rename = fail_rename
        self.mkdirs_calls: list[str] = []
        self.remove_calls: list[str] = []

    def mkdirs(self, *, mount: dict, normalized_path: str) -> None:
        _ = mount
        self.mkdirs_calls.append(normalized_path)

    @contextlib.contextmanager
    def open_write(self, *, mount: dict, normalized_path: str):
        _ = mount
        buffer = io.BytesIO()
        try:
            yield buffer
        finally:
            self.files[normalized_path] = buffer.getvalue()

    @contextlib.contextmanager
    def open_read(self, *, mount: dict, normalized_path: str):
        _ = mount
        if normalized_path not in self.files:
            raise _not_found()
        yield io.BytesIO(self.files[normalized_path])

    def rename(
        self,
        *,
        mount: dict,
        src_normalized_path: str,
        dst_normalized_path: str,
    ) -> None:
        _ = mount
        if self.fail_rename:
            raise MountProviderError(
                failure_class="mount.rename.failed",
                next_action_hint="Retry the operation.",
                public_message="Rename failed.",
                public_code="mount.rename.failed",
            )
        if src_normalized_path not in self.files:
            raise _not_found()
        self.files[dst_normalized_path] = self.files.pop(src_normalized_path)

    def remove(self, *, mount: dict, normalized_path: str) -> None:
        _ = mount
        self.remove_calls.append(normalized_path)
        if normalized_path not in self.files:
            raise _not_found()
        self.files.pop(normalized_path)


def test_write_mount_stream_transaction_cleans_partial_temp_when_limit_fails():
    provider = _MemoryMountProvider()

    with pytest.raises(MountWriteTooLarge):
        write_mount_stream_transaction(
            provider=provider,
            mount={},
            temp_path="/.tmp",
            final_path="/final.txt",
            chunks=[b"abc", b"def"],
            limits=MountWriteLimits(max_bytes=3),
            parent_path="/",
        )

    assert "/.tmp" not in provider.files
    assert "/final.txt" not in provider.files
    assert provider.mkdirs_calls == ["/"]
    assert provider.remove_calls == ["/.tmp", "/.tmp"]


def test_write_mount_stream_transaction_cleans_temp_when_final_rename_fails():
    provider = _MemoryMountProvider(fail_rename=True)

    with pytest.raises(MountProviderError) as exc_info:
        write_mount_stream_transaction(
            provider=provider,
            mount={},
            temp_path="/.tmp",
            final_path="/final.txt",
            chunks=[b"payload"],
        )

    assert exc_info.value.public_code == "mount.rename.failed"
    assert "/.tmp" not in provider.files
    assert "/final.txt" not in provider.files
    assert provider.remove_calls == ["/.tmp", "/.tmp"]


def test_copy_mount_file_transaction_streams_via_temp_and_final_rename():
    provider = _MemoryMountProvider(files={"/source.txt": b"payload"})

    result = copy_mount_file_transaction(
        provider=provider,
        mount={},
        source_path="/source.txt",
        temp_path="/.tmp",
        final_path="/copy.txt",
    )

    assert result.bytes_written == len(b"payload")
    assert provider.files == {
        "/source.txt": b"payload",
        "/copy.txt": b"payload",
    }
    assert provider.remove_calls == ["/.tmp"]
