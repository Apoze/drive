"""Direct contract tests for the core app configuration hook."""

from __future__ import annotations

import sys

import core
from core.apps import CoreConfig


def test_core_config_ready_imports_signals(monkeypatch):
    """`CoreConfig.ready()` imports the local `signals` module."""

    monkeypatch.delitem(sys.modules, "core.signals", raising=False)
    monkeypatch.delattr(core, "signals", raising=False)

    CoreConfig("core", core).ready()

    assert "core.signals" in sys.modules
