from __future__ import annotations

import json
from pathlib import Path

from dp.core.verify import run_goal_backward_verify


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_verify_report_verified(tmp_path: Path) -> None:
    _write(tmp_path / "artifacts/evidence.txt", "ok")
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [{"id": "A1", "path": "./artifacts/evidence.txt"}],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "verified"
    assert [level.status for level in report.levels] == ["verified", "verified", "verified"]


def test_verify_report_incomplete_when_levels_missing(tmp_path: Path) -> None:
    _write(tmp_path / "manifest.json", json.dumps({"truths": [], "artifacts": [], "links": []}))

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "incomplete"
    assert [level.status for level in report.levels] == ["incomplete", "incomplete", "incomplete"]


def test_verify_report_failed_on_unresolved_items(tmp_path: Path) -> None:
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": False}],
                "artifacts": [{"id": "A1", "path": "missing.txt"}],
                "links": [{"truth_id": "T1", "artifact_id": "A2"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "failed"
    assert [level.status for level in report.levels] == ["failed", "failed", "failed"]
