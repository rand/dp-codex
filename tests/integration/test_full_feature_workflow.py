from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Sequence

import pytest

from dp.providers.beads import CommandResult


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_full_feature_workflow_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    cli_main = importlib.import_module("dp.cli.main")
    monkeypatch.chdir(tmp_path)

    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=0, stdout='{"id":"dpcx-egm.9"}\n', stderr="")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    task_exit = cli_main.main(
        [
            "task",
            "discover",
            "dpcx-egm.3.1",
            "Implement full feature workflow",
            "--json",
        ]
    )
    assert task_exit == 0
    task_payload = json.loads(capsys.readouterr().out)
    assert task_payload["ok"] is True

    _write(tmp_path / "docs/specs/feature.md", "[SPEC-01.01]")
    _write(tmp_path / "dp/core/feature.py", "# @trace SPEC-01.01")

    coverage_exit = cli_main.main(
        [
            "trace",
            "coverage",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
        ]
    )
    assert coverage_exit == 0
    coverage_payload = json.loads(capsys.readouterr().out)
    assert coverage_payload["total_specs"] == 1
    assert coverage_payload["covered_count"] == 1

    validate_exit = cli_main.main(
        [
            "trace",
            "validate",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
        ]
    )
    assert validate_exit == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["valid"] is True

    review_exit = cli_main.main(["review", "--json"])
    assert review_exit == 0
    review_payload = json.loads(capsys.readouterr().out)
    assert review_payload["ready_to_commit"] is True

    _write(tmp_path / "artifacts/proof.txt", "ok")
    _write(
        tmp_path / "docs/verify/manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [{"id": "A1", "path": "artifacts/proof.txt"}],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )
    verify_exit = cli_main.main(["verify", "--manifest", "docs/verify/manifest.json", "--json"])
    assert verify_exit == 0
    verify_payload = json.loads(capsys.readouterr().out)
    assert verify_payload["outcome"] == "verified"
