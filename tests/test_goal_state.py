from __future__ import annotations

import json
from pathlib import Path

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
    assert "not implemented yet" in payload["message"]
