"""MountProvider conversion remains intentionally unsupported in B0074."""

# pylint: disable=missing-function-docstring

from core.mounts.providers.base import MountEntry
from core.services.mount_capabilities import (
    MountProviderIoCapabilities,
    build_mount_entry_abilities,
)


def test_mount_entry_abilities_do_not_expose_convert():
    abilities = build_mount_entry_abilities(
        entry=MountEntry(
            normalized_path="/legacy.doc",
            name="legacy.doc",
            entry_type="file",
            size=10,
            modified_at=None,
        ),
        mount_capabilities={
            "mount.preview": True,
            "mount.wopi": True,
            "mount.duplicate": True,
            "mount.share_link": True,
        },
        io_capabilities=MountProviderIoCapabilities(
            stat=True,
            open_read=True,
            open_write=True,
            rename=True,
            remove=True,
            mkdirs=True,
            range_reads=True,
            browser_stream_mode="native",
            head_metadata=True,
            stable_version=True,
        ),
        preview_candidate=True,
        wopi_supported=True,
    )

    assert "convert" not in abilities
