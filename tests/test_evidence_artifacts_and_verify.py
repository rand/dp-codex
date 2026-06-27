from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import dp.core.evidence_run as evidence_run
from dp.cli.main import main

SOURCE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"


def test_evidence_run_writes_output_artifact(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "evidence",
            "run",
            "evidence/plan.json",
            "--output",
            "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    output_path = tmp_path / "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"
    assert output_path.exists()
    assert payload["ok"] is True
    assert payload["artifact"] == {
        "path": "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json",
        "written": True,
    }
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_evidence_run_rejects_unsafe_output_before_execution(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)

    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("evidence checks must not run for invalid output paths")

    monkeypatch.setattr(evidence_run.subprocess, "run", fail_if_called)

    exit_code = main(
        ["evidence", "run", "evidence/plan.json", "--output", "../run.json", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["checks"] == []
    assert payload["error"]["code"] == "invalid_output_path"


def test_evidence_run_refuses_existing_output_without_force(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    output_path = "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"

    assert main(["evidence", "run", "evidence/plan.json", "--output", output_path, "--json"]) == 0
    capsys.readouterr()

    second_exit = main(["evidence", "run", "evidence/plan.json", "--output", output_path, "--json"])

    assert second_exit == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "output_exists"

    forced_exit = main(
        [
            "evidence",
            "run",
            "evidence/plan.json",
            "--output",
            output_path,
            "--force",
            "--json",
        ]
    )
    assert forced_exit == 0


def test_verify_goal_runs_evidence_writes_artifact_and_verifies(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["verify", "--goal", "goal.json", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "verify.goal"
    assert payload["goal_id"] == "GOAL-SPEC-70.01"
    assert payload["evidence"]["path"] == "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"
    assert payload["stages"]["goal_lint"]["exit_code"] == 0
    assert payload["stages"]["evidence_lint"]["exit_code"] == 0
    assert payload["stages"]["evidence_run"]["exit_code"] == 0
    assert payload["stages"]["trace"]["ok"] is True
    assert payload["stages"]["goal_verify"]["exit_code"] == 0
    assert (tmp_path / "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json").exists()

    event_log = tmp_path / ".dp/goals/events.jsonl"
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["event"] == "verified"
    assert events[-1]["evidence"] == "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"


def test_verify_goal_uses_supplied_evidence_without_running_checks(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    output_path = "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"
    assert main(["evidence", "run", "evidence/plan.json", "--output", output_path, "--json"]) == 0
    capsys.readouterr()

    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("supplied evidence mode must not execute evidence checks")

    monkeypatch.setattr(evidence_run.subprocess, "run", fail_if_called)

    exit_code = main(["verify", "--goal", "goal.json", "--evidence", output_path, "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stages"]["evidence_run"] is None
    assert payload["stages"]["goal_verify"]["exit_code"] == 0


def test_verify_goal_writes_failed_run_but_does_not_verify(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    plan_path = tmp_path / "evidence/plan.json"
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["checks"][0]["assertions"] = [
        {"type": "json_path_equals", "path": "$.valid", "value": False}
    ]
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    exit_code = main(["verify", "--goal", "goal.json", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["stages"]["evidence_run"]["exit_code"] == 1
    assert payload["stages"]["goal_verify"] is None
    run_path = tmp_path / "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"
    assert run_path.exists()
    assert json.loads(run_path.read_text(encoding="utf-8"))["ok"] is False
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_verify_goal_rejects_stale_supplied_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    output_path = "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json"
    assert main(["evidence", "run", "evidence/plan.json", "--output", output_path, "--json"]) == 0
    capsys.readouterr()
    plan_path = tmp_path / "evidence/plan.json"
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["checks"][0]["timeout_seconds"] = 31
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    exit_code = main(["verify", "--goal", "goal.json", "--evidence", output_path, "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stages"]["goal_verify"]["payload"]["error"]["code"] == "stale_evidence_plan"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def _write_verifiable_goal_and_plan(tmp_path: Path) -> None:
    goal_payload = json.loads(SOURCE_GOAL.read_text(encoding="utf-8"))
    goal_payload["evidence"]["evidence_plan"] = "evidence/plan.json"
    goal_payload["evidence"]["trace_ids"] = ["SPEC-70.01"]
    (tmp_path / "goal.json").write_text(json.dumps(goal_payload), encoding="utf-8")

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "plan.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "EVIDENCE-SPEC-70.01",
                "goal_id": "GOAL-SPEC-70.01",
                "checks": [
                    {
                        "id": "goal-lint-valid",
                        "kind": "registered_command",
                        "argv": ["dp", "goal", "lint", "goal.json", "--json"],
                        "timeout_seconds": 30,
                        "success_exit_codes": [0],
                        "assertions": [
                            {"type": "exit_code_in", "values": [0]},
                            {"type": "stdout_json"},
                            {"type": "json_path_equals", "path": "$.valid", "value": True},
                            {"type": "stderr_empty"},
                        ],
                        "mutation_policy": "read_only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
