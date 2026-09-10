"""Run with python3 -m unittest discover -s docker/suite/tests -p test_prepare_documents.py."""

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_documents import prepare


class DocumentConfigurationTest(unittest.TestCase):
    def test_replay_preserves_existing_settings_and_detects_key_divergence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state, drive = root / "suite", root / "drive"
            (state / "docs").mkdir(parents=True)
            (drive / "env.d/development").mkdir(parents=True)
            (state / "settings.json").write_text(json.dumps({"host": "192.0.2.10"}))
            source_env = drive / "env.d/development/common.local"
            native_env = state / "docs/backend.env"
            for path in (source_env, native_env):
                path.write_text("EXISTING_SETTING=keep\n")
            prepare(state, drive, uid=os.getuid())
            key = drive / "data/storage-secrets/docs-documents/inbound_read"
            retained = key.read_bytes()
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            prepare(state, drive, mode="enable", uid=os.getuid())
            prepare(state, drive, uid=os.getuid())
            self.assertEqual(key.read_bytes(), retained)
            for path in (source_env, native_env):
                self.assertIn("EXISTING_SETTING=keep\n", path.read_text())
                self.assertIn("DOCS_DRIVE_ENABLED=true\n", path.read_text())
            native_key = state / "docs/keys/documents/outbound_read"
            self.assertEqual(native_key.read_bytes(), retained)
            native_key.write_text("deliberately-divergent" * 3)
            with self.assertRaisesRegex(ValueError, "differ"):
                prepare(state, drive, uid=os.getuid())
            self.assertEqual(key.read_bytes(), retained)
