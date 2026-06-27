from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import dp.core.evidence_run as evidence_run
from dp.cli.main import main

FIXTURE_DIR = Path("tests/fixtures/evidence")


def test_evidence_run_executes_valid_registered_fixture(capsys) -> None:
    exit_code = main(
        ["evidence", "run", (FIXTURE_DIR / "valid_run_goal_lint.json").as_posix(), "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "evidence.run"
    assert payload["evidence_id"] == "EVIDENCE-SPEC-80.08-RUN"
    assert payload["goal_id"] == "GOAL-SPEC-80.08"
    assert payload["summary"] == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "timed_out": 0,
        "errored": 0,
    }
    assert payload["checks"][0]["status"] == "passed"
    assert payload["checks"][0]["argv"][:3] == ["dp", "goal", "lint"]
    assert all(assertion["ok"] is True for assertion in payload["checks"][0]["assertions"])


def test_evidence_run_denies_unregistered_plan_without_executing(capsys) -> None:
    exit_code = main(
        [
            "evidence",
            "run",
            (FIXTURE_DIR / "invalid_unregistered_command.json").as_posix(),
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["checks"] == []
    assert payload["error"]["code"] == "invalid_evidence_plan"
    assert "unregistered_command" in {error["code"] for error in payload["lint"]["errors"]}


def test_evidence_run_denies_raw_shell_plan_without_executing(capsys) -> None:
    exit_code = main(
        ["evidence", "run", (FIXTURE_DIR / "invalid_raw_shell_string.json").as_posix(), "--json"]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"] == []
    assert "raw_shell_prohibited" in {error["code"] for error in payload["lint"]["errors"]}


def test_evidence_run_reports_assertion_failure(capsys) -> None:
    exit_code = main(
        [
            "evidence",
            "run",
            (FIXTURE_DIR / "invalid_run_assertion_failure.json").as_posix(),
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["summary"]["failed"] == 1
    assert payload["checks"][0]["status"] == "failed"
    assert any(assertion["ok"] is False for assertion in payload["checks"][0]["assertions"])


def test_evidence_run_reports_missing_file_as_input_error(capsys) -> None:
    exit_code = main(["evidence", "run", "tests/fixtures/evidence/missing.json", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"] == []
    assert payload["lint"]["errors"][0]["code"] == "missing_file"


def test_evidence_run_enforces_existing_relative_cwd(tmp_path: Path, capsys) -> None:
    plan = tmp_path / "evidence.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "EVIDENCE-SPEC-80.08-CWD",
                "goal_id": "GOAL-SPEC-80.08",
                "checks": [
                    {
                        "id": "missing-cwd",
                        "kind": "registered_command",
                        "argv": ["dp", "doctor", "--json"],
                        "cwd": "does-not-exist",
                        "timeout_seconds": 30,
                        "success_exit_codes": [0],
                        "assertions": [{"type": "exit_code_in", "values": [0]}],
                        "mutation_policy": "read_only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["evidence", "run", plan.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"][0]["status"] == "error"
    assert payload["checks"][0]["error"]["code"] == "cwd_not_found"


def test_evidence_run_uses_shell_false_and_timeout(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    plan = tmp_path / "evidence.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "EVIDENCE-SPEC-80.08-TIMEOUT",
                "goal_id": "GOAL-SPEC-80.08",
                "checks": [
                    {
                        "id": "timeout",
                        "kind": "registered_command",
                        "argv": ["dp", "doctor", "--json"],
                        "timeout_seconds": 7,
                        "success_exit_codes": [0],
                        "assertions": [{"type": "exit_code_in", "values": [0]}],
                        "mutation_policy": "read_only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    observed: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed["argv"] = args[0]
        observed["shell"] = kwargs["shell"]
        observed["timeout"] = kwargs["timeout"]
        observed["capture_output"] = kwargs["capture_output"]
        observed["text"] = kwargs["text"]
        observed["env_keys"] = sorted(kwargs["env"])
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(evidence_run.subprocess, "run", fake_run)

    exit_code = main(["evidence", "run", plan.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert observed["argv"] == ["dp", "doctor", "--json"]
    assert observed["shell"] is False
    assert observed["timeout"] == 7
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert "PATH" in observed["env_keys"]
    assert payload["checks"][0]["status"] == "timed_out"
