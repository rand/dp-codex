from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main

SOURCE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"


def _copy_goal(tmp_path: Path) -> Path:
    goal_path = tmp_path / "goal.json"
    goal_path.write_text(SOURCE_GOAL.read_text(encoding="utf-8"), encoding="utf-8")
    return goal_path


def test_goal_state_lifecycle_records_append_only_events(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _copy_goal(tmp_path)
    monkeypatch.chdir(tmp_path)

    claim_exit = main(["goal", "claim", goal_path.as_posix(), "--agent", "codex", "--json"])
    assert claim_exit == 0
    claim_payload = json.loads(capsys.readouterr().out)
    assert claim_payload["state"] == "claimed"
    assert claim_payload["lease"]["holder"] == "codex"

    start_exit = main(["goal", "start", goal_path.as_posix(), "--agent", "codex", "--json"])
    assert start_exit == 0
    start_payload = json.loads(capsys.readouterr().out)
    assert start_payload["state"] == "started"

    heartbeat_exit = main(["goal", "heartbeat", goal_path.as_posix(), "--json"])
    assert heartbeat_exit == 0
    heartbeat_payload = json.loads(capsys.readouterr().out)
    assert heartbeat_payload["state"] == "pursuing"

    block_exit = main(
        ["goal", "block", goal_path.as_posix(), "--reason", "needs_decision", "--json"]
    )
    assert block_exit == 0
    block_payload = json.loads(capsys.readouterr().out)
    assert block_payload["state"] == "blocked"
    assert block_payload["blocked"]["reason"] == "needs_decision"

    release_exit = main(
        ["goal", "release", goal_path.as_posix(), "--reason", "context reset", "--json"]
    )
    assert release_exit == 0
    release_payload = json.loads(capsys.readouterr().out)
    assert release_payload["state"] == "released"

    event_log = tmp_path / ".dp/goals/events.jsonl"
    assert event_log.exists()
    assert len(event_log.read_text(encoding="utf-8").splitlines()) == 5


def test_goal_claim_rejects_non_stale_claim_by_another_agent(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _copy_goal(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["goal", "claim", goal_path.as_posix(), "--agent", "codex", "--json"]) == 0
    capsys.readouterr()

    exit_code = main(["goal", "claim", goal_path.as_posix(), "--agent", "other", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "goal_already_claimed"


def test_goal_status_detects_stale_lease(tmp_path: Path, monkeypatch, capsys) -> None:
    goal_path = _copy_goal(tmp_path)
    monkeypatch.chdir(tmp_path)
    event_log = tmp_path / ".dp/goals/events.jsonl"
    event_log.parent.mkdir(parents=True)
    event_log.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "event": "claimed",
                "goal_id": "GOAL-SPEC-70.01",
                "goal_path": goal_path.as_posix(),
                "timestamp": "2000-01-01T00:00:00Z",
                "agent": "codex",
                "lease_expires_at": "2000-01-01T01:00:00Z",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["goal", "status", goal_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lease"]["stale"] is True
    assert payload["state"] == "released"


def test_goal_complete_records_evidence_pending_without_verifying(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _copy_goal(tmp_path)
    evidence_path = tmp_path / "evidence/run.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text('{"ok": true}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["goal", "complete", goal_path.as_posix(), "--evidence", "evidence/run.json", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "evidence_pending"
    assert payload["evidence_status"] == "pending_verification"
    assert "dp goal verify" in payload["message"]


def test_goal_verify_records_verified_from_matching_evidence_run(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)

    exit_code = main(["goal", "verify", "goal.json", "--evidence", run_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "verified"
    assert payload["evidence_status"] == "verified"
    assert payload["evidence_id"] == "EVIDENCE-SPEC-70.01"
    assert payload["evidence_plan"] == "evidence/plan.json"
    assert payload["last_event"]["event"] == "verified"
    assert payload["last_event"]["evidence"] == "runs/run.json"
    assert payload["last_event"]["evidence_plan"] == "evidence/plan.json"


def test_goal_verify_rejects_failed_evidence_run_without_event(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    run_payload["ok"] = False
    run_payload["error"] = {
        "code": "evidence_checks_failed",
        "path": "$.checks",
        "message": "One or more evidence checks failed.",
    }
    run_payload["checks"][0]["ok"] = False
    run_payload["checks"][0]["status"] = "failed"
    run_payload["summary"] = {
        "total": 1,
        "passed": 0,
        "failed": 1,
        "timed_out": 0,
        "errored": 0,
    }
    run_path.write_text(json.dumps(run_payload), encoding="utf-8")

    exit_code = main(["goal", "verify", "goal.json", "--evidence", run_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "evidence_run_failed"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_verify_rejects_mismatched_goal_id(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    run_payload["goal_id"] = "GOAL-OTHER"
    run_payload["lint"]["goal_id"] = "GOAL-OTHER"
    run_path.write_text(json.dumps(run_payload), encoding="utf-8")

    exit_code = main(["goal", "verify", "goal.json", "--evidence", run_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "goal_id_mismatch"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_verify_rejects_stale_evidence_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)
    plan_path = tmp_path / "evidence/plan.json"
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_payload["checks"][0]["timeout_seconds"] = 31
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    exit_code = main(["goal", "verify", "goal.json", "--evidence", run_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "stale_evidence_plan"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_verify_rejects_missing_evidence_run(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["goal", "verify", "goal.json", "--evidence", "runs/missing.json", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "missing_evidence_path"


def test_goal_verify_rejects_agent_self_report_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = tmp_path / "runs/run.json"
    run_path.parent.mkdir()
    run_path.write_text('{"ok": true, "message": "done"}\n', encoding="utf-8")

    exit_code = main(["goal", "verify", "goal.json", "--evidence", "runs/run.json", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "invalid_evidence_run"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def _write_verifiable_goal_and_plan(tmp_path: Path) -> None:
    goal_payload = json.loads(SOURCE_GOAL.read_text(encoding="utf-8"))
    goal_payload["evidence"]["evidence_plan"] = "evidence/plan.json"
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


def _write_successful_evidence_run(capsys: Any) -> Path:
    exit_code = main(["evidence", "run", "evidence/plan.json", "--json"])
    assert exit_code == 0
    run_path = Path("runs/run.json")
    run_path.parent.mkdir()
    run_path.write_text(capsys.readouterr().out, encoding="utf-8")
    return run_path
