from __future__ import annotations

import hashlib
import json
from pathlib import Path

from dp.core.verify import run_goal_backward_verify

# @trace SPEC-70.04


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


def test_verify_report_validates_structured_artifact_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "artifacts/evidence.txt"
    _write(evidence_path, "ok")
    digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [
                    {
                        "id": "A1",
                        "path": "./artifacts/evidence.txt",
                        "sha256": f"sha256:{digest}",
                        "command": {
                            "argv": ["pytest", "tests/unit/test_verify.py"],
                            "cwd": ".",
                            "exit_code": 0,
                            "success_exit_codes": [0],
                        },
                        "task_id": "dpcx-ea9.3",
                        "spec_id": "SPEC-70.04",
                    }
                ],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "verified"
    assert [level.status for level in report.levels] == ["verified", "verified", "verified"]


def test_verify_report_fails_on_hash_mismatch(tmp_path: Path) -> None:
    _write(tmp_path / "artifacts/evidence.txt", "actual")
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [
                    {
                        "id": "A1",
                        "path": "./artifacts/evidence.txt",
                        "sha256": "sha256:" + ("0" * 64),
                    }
                ],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "failed"
    artifact_level = report.levels[1]
    assert artifact_level.status == "failed"
    assert artifact_level.passed == 0
    assert any("sha256 mismatch" in detail for detail in artifact_level.details)


def test_verify_report_fails_on_shell_command_string(tmp_path: Path) -> None:
    _write(tmp_path / "artifacts/evidence.txt", "ok")
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [
                    {
                        "id": "A1",
                        "path": "./artifacts/evidence.txt",
                        "command": "pytest tests/unit/test_verify.py",
                    }
                ],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "failed"
    assert any("not a shell string" in detail for detail in report.levels[1].details)


def test_verify_report_fails_on_failed_command_record(tmp_path: Path) -> None:
    _write(tmp_path / "artifacts/evidence.txt", "ok")
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [
                    {
                        "id": "A1",
                        "path": "./artifacts/evidence.txt",
                        "command": {
                            "argv": ["make", "check"],
                            "exit_code": 2,
                            "success_exit_codes": [0],
                        },
                    }
                ],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "failed"
    assert any("is not in success_exit_codes" in detail for detail in report.levels[1].details)


def test_verify_report_fails_on_bad_task_or_spec_ids(tmp_path: Path) -> None:
    _write(tmp_path / "artifacts/evidence.txt", "ok")
    _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [
                    {
                        "id": "A1",
                        "path": "./artifacts/evidence.txt",
                        "task_id": "not a task",
                        "spec_id": "SPEC-7.4",
                    }
                ],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    report = run_goal_backward_verify(tmp_path / "manifest.json")

    assert report.outcome == "failed"
    assert any("task_id" in detail for detail in report.levels[1].details)
    assert any("spec_id" in detail for detail in report.levels[1].details)


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
