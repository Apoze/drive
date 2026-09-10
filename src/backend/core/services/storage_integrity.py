"""Bounded transfer checksums shared by native S3 moves and renames."""

import hashlib
from contextlib import closing

from core.services.mount_write_transaction import same_mount_entry
from core.services.storage_quota import StorageWriteConflict


class DigestReader:
    """Hash bounded reads without buffering the file or interpreting S3 ETags."""

    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size):
        """Preserve the underlying stream's short-read semantics."""
        value = self.stream.read(size)
        self.digest.update(value)
        self.size += len(value)
        return value


def verify_s3_digest(client, bucket, key, head, expected):
    """Verify an observed destination version without treating ETag as a checksum."""
    version = head.get("VersionId")
    with closing(
        client.get_object(
            Bucket=bucket,
            Key=key,
            IfMatch=head["ETag"],
            **({"VersionId": version} if version not in {None, "", "null"} else {}),
        )["Body"]
    ) as body:
        reader = DigestReader(body)
        while reader.read(1024 * 1024):
            pass
    if reader.digest.hexdigest() != expected:
        raise StorageWriteConflict("Destination checksum differs; the source was retained.")


def verify_mount_digest(provider, mount, path, entry, expected):
    """Re-read a native destination and reject replacement or modification during the read."""
    with provider.open_read(mount=mount, normalized_path=path) as stream:
        reader = DigestReader(stream)
        while reader.read(1024 * 1024):
            pass
    current = provider.stat(mount=mount, normalized_path=path)
    if reader.digest.hexdigest() != expected or not same_mount_entry(entry, current):
        raise StorageWriteConflict("Destination checksum differs; the source was retained.")
