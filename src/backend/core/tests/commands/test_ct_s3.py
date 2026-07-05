"""Tests for deterministic CT-S3 command artifacts and exit status."""
# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from io import StringIO

from django.core.management import call_command

import pytest


def test_ct_s3_command_writes_artifacts_and_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "core.management.commands.ct_s3.run_ct_s3",
        lambda **_kwargs: {
            "run_id": "run-1",
            "gate_id": "s3.contracts.seaweedfs-s3",
            "overall_ok": True,
            "results": [],
        },
    )
    monkeypatch.setattr(
        "core.management.commands.ct_s3.render_human_report",
        lambda report: f"report for {report['run_id']}\n",
    )
    monkeypatch.setattr(
        "core.management.commands.ct_s3.dumps_json",
        lambda report: '{"run_id":"%s"}\n' % report["run_id"],
    )

    stdout = StringIO()
    call_command(
        "ct_s3",
        profile="seaweedfs-s3",
        out_dir=str(tmp_path),
        run_id="run-1",
        stdout=stdout,
    )

    run_dir = tmp_path / "run-1-seaweedfs-s3"
    assert (run_dir / "report.md").read_text(encoding="utf-8") == "report for run-1\n"
    assert (run_dir / "report.json").read_text(encoding="utf-8") == '{"run_id":"run-1"}\n'
    assert (tmp_path / "latest.txt").read_text(encoding="utf-8") == "run-1-seaweedfs-s3\n"
    assert "CT-S3: PASS" in stdout.getvalue()


def test_ct_s3_command_writes_artifacts_and_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "core.management.commands.ct_s3.run_ct_s3",
        lambda **_kwargs: {
            "run_id": "run-2",
            "gate_id": "s3.contracts.seaweedfs-s3",
            "overall_ok": False,
            "results": [],
        },
    )
    monkeypatch.setattr(
        "core.management.commands.ct_s3.render_human_report",
        lambda report: f"report for {report['run_id']}\n",
    )
    monkeypatch.setattr(
        "core.management.commands.ct_s3.dumps_json",
        lambda report: '{"run_id":"%s"}\n' % report["run_id"],
    )

    stderr = StringIO()
    with pytest.raises(SystemExit, match="1"):
        call_command(
            "ct_s3",
            profile="seaweedfs-s3",
            out_dir=str(tmp_path),
            run_id="run-2",
            stderr=stderr,
        )

    run_dir = tmp_path / "run-2-seaweedfs-s3"
    assert (run_dir / "report.md").read_text(encoding="utf-8") == "report for run-2\n"
    assert (run_dir / "report.json").read_text(encoding="utf-8") == '{"run_id":"run-2"}\n'
    assert (tmp_path / "latest.txt").read_text(encoding="utf-8") == "run-2-seaweedfs-s3\n"
    assert "CT-S3: FAIL" in stderr.getvalue()
