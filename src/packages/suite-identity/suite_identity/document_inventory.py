"""Private, bounded indexing of the native migration's immutable JSONL metadata."""

import hashlib
import json
import os
import sqlite3
import stat
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder


@contextmanager
def indexed_inventory(filename):
    """Validate the entire receipt before yielding any records to a mutating caller."""
    path = Path(filename)
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("Use a private regular inventory file (mode 0600).")
    with TemporaryDirectory(prefix="docs-migration-") as directory:
        database = sqlite3.connect(str(Path(directory) / "inventory.sqlite3"))
        (Path(directory) / "inventory.sqlite3").chmod(0o600)
        database.row_factory = sqlite3.Row
        try:
            database.execute("CREATE TABLE records (kind TEXT, document TEXT, user TEXT, path TEXT, object_key TEXT, data TEXT)")
            digest, counts, checkpoint, receipt = hashlib.sha256(), Counter(), None, None
            batch = []
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
                while line := stream.readline(1024 * 1024 + 1):
                    if len(line) > 1024 * 1024 or receipt is not None:
                        raise ValueError("Invalid inventory size or trailing data.")
                    try:
                        row = json.loads(line)
                    except (ValueError, UnicodeError):
                        raise ValueError("Invalid or interrupted inventory.") from None
                    if not isinstance(row, dict) or not isinstance(row.get("kind"), str):
                        raise ValueError("Invalid inventory record.")
                    kind = row["kind"]
                    if checkpoint is None:
                        if kind != "checkpoint" or row.get("format") != 1:
                            raise ValueError("Unsupported inventory checkpoint.")
                        checkpoint = row
                    elif kind == "checkpoint":
                        raise ValueError("Duplicate inventory checkpoint.")
                    if kind == "receipt":
                        if row.get("sha256") != digest.hexdigest() or row.get("counts") != dict(counts):
                            raise ValueError("Inventory checksum or counts do not match.")
                        receipt = row
                        continue
                    digest.update(line)
                    if kind == "checkpoint":
                        continue
                    counts[kind] += 1
                    batch.append((kind, row.get("id") if kind == "document" else row.get("document_id"),
                                  row.get("id") if kind == "user" else row.get("user_id"), row.get("path"), row.get("Key"), line.decode()))
                    if len(batch) == 500:
                        database.executemany("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)", batch)
                        batch.clear()
            if receipt is None:
                raise ValueError("Inventory has no completion receipt.")
            database.executemany("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?)", batch)
            for column in ("document", "user", "path", "object_key"):
                database.execute(f"CREATE INDEX by_{column} ON records(kind, {column})")
            database.execute("CREATE UNIQUE INDEX unique_document_id ON records(document) WHERE kind = 'document'")
            database.execute("CREATE UNIQUE INDEX unique_document_path ON records(path) WHERE kind = 'document'")
            database.commit()
            yield database, checkpoint, receipt
        finally:
            database.close()


def records(database, kind, *, document=None, user=None, path=None, object_key=None):
    """Stream metadata selected by fixed indexed columns."""
    clauses, arguments = ["kind = ?"], [kind]
    for column, value in (("document", document), ("user", user), ("path", path), ("object_key", object_key)):
        if value is not None:
            clauses.append(f"{column} = ?")
            arguments.append(str(value))
    cursor = database.execute("SELECT data FROM records WHERE " + " AND ".join(clauses), arguments)
    for row in cursor:
        yield json.loads(row["data"])


def write_artifact(output, checkpoint, rows):
    """An interrupted plan lacks a receipt and can never be applied."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise CommandError("Use a private plan directory (mode 0700).")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise CommandError("The plan already exists; choose a new path.") from None
    digest, counts = hashlib.sha256(), Counter()
    with os.fdopen(descriptor, "wb") as stream:

        def emit(row):
            raw = (json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True) + "\n").encode()
            stream.write(raw)
            digest.update(raw)

        emit({"kind": "checkpoint", "format": 1, "schema": "drive-docs-migration", **checkpoint})
        for row in rows:
            emit(row)
            counts[row["kind"]] += 1
        emit({"kind": "receipt", "sha256": digest.hexdigest(), "counts": dict(counts)})
        stream.flush()
        os.fsync(stream.fileno())
    return counts
