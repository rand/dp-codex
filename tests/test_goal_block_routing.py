from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main
from dp.providers.beads import CommandResult

SOURCE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"


def test_goal_block_write_artifact_creates_spec_stub_and_records_event(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, beads=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "goal",
            "block",
            goal_path.as_posix(),
            "--reason",
            "needs_specification",
            "--write-artifact",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    routing = payload["blocked"]["routing"]
    assert payload["ok"] is True
    assert payload["state"] == "blocked"
    assert routing["ok"] is True
    assert routing["action"] == "create_spec_stub"
    assert routing["artifact"]["kind"] == "spec"
    artifact_path = tmp_path / routing["artifact"]["path"]
    assert artifact_path.exists()
    assert "[SPEC-80.14]" in artifact_path.read_text(encoding="utf-8")
    assert routing["beads"]["requested"] is False

    event = _last_goal_event(tmp_path)
    assert event["event"] == "blocked"
    assert event["reason"] == "needs_specification"
    assert event["routing"]["artifact"]["path"] == routing["artifact"]["path"]


def test_goal_block_write_artifact_creates_lintable_evidence_stub(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, beads=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "goal",
            "block",
            goal_path.as_posix(),
            "--reason",
            "needs_validator",
            "--write-artifact",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    evidence_path = payload["blocked"]["routing"]["artifact"]["path"]

    lint_exit = main(["evidence", "lint", evidence_path, "--json"])

    assert lint_exit == 0
    lint_payload = json.loads(capsys.readouterr().out)
    assert lint_payload["valid"] is True
    assert lint_payload["goal_id"] == "GOAL-SPEC-70.01"


def test_goal_block_write_artifact_creates_adr_and_beads_followup(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, beads=True)
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run_bd(args: list[str]) -> CommandResult:
        calls.append(args)
        return CommandResult(returncode=0, stdout='{"id": "dpcx-route"}\n', stderr="")

    monkeypatch.setattr("dp.core.blocker_routing.run_bd", fake_run_bd)

    exit_code = main(
        [
            "goal",
            "block",
            goal_path.as_posix(),
            "--reason",
            "needs_decision",
            "--write-artifact",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    routing = payload["blocked"]["routing"]
    assert routing["artifact"]["kind"] == "adr"
    assert routing["artifact"]["path"].startswith("docs/adr/ADR-")
    assert (tmp_path / routing["artifact"]["path"]).exists()
    assert routing["beads"]["requested"] is True
    assert routing["beads"]["ok"] is True
    assert routing["beads"]["issue_id"] == "dpcx-route"
    assert calls and calls[0][0] == "create"
    assert "--json" in calls[0]


def test_goal_block_write_artifact_records_missing_route_without_losing_block(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, beads=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "goal",
            "block",
            goal_path.as_posix(),
            "--reason",
            "budget_exhausted",
            "--write-artifact",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["state"] == "blocked"
    assert payload["error"]["code"] == "missing_blocked_route"
    assert payload["blocked"]["reason"] == "budget_exhausted"
    assert payload["blocked"]["routing"]["ok"] is False
    assert _last_goal_event(tmp_path)["routing"]["error"]["code"] == "missing_blocked_route"


def test_goal_block_write_artifact_refuses_changed_deterministic_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, beads=False)
    collision = tmp_path / "docs/specs/BLOCKER-GOAL-SPEC-70-01-needs-specification.md"
    collision.parent.mkdir(parents=True)
    collision.write_text("human-edited blocker stub\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "goal",
            "block",
            goal_path.as_posix(),
            "--reason",
            "needs_specification",
            "--write-artifact",
            "--json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "artifact_exists"
    assert collision.read_text(encoding="utf-8") == "human-edited blocker stub\n"
    assert _last_goal_event(tmp_path)["routing"]["error"]["code"] == "artifact_exists"


def test_goal_block_write_artifact_records_beads_failure_after_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, beads=True)
    monkeypatch.chdir(tmp_path)

    def fake_run_bd(args: list[str]) -> CommandResult:
        return CommandResult(returncode=1, stdout="", stderr="beads create failed")

    monkeypatch.setattr("dp.core.blocker_routing.run_bd", fake_run_bd)

    exit_code = main(
        [
            "goal",
            "block",
            goal_path.as_posix(),
            "--reason",
            "needs_validator",
            "--write-artifact",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    routing = payload["blocked"]["routing"]
    assert payload["state"] == "blocked"
    assert routing["artifact"]["kind"] == "evidence_plan"
    assert (tmp_path / routing["artifact"]["path"]).exists()
    assert routing["beads"]["requested"] is True
    assert routing["beads"]["ok"] is False
    assert routing["beads"]["error"]["code"] == "beads_create_failed"
    assert _last_goal_event(tmp_path)["routing"]["beads"]["error"]["code"] == "beads_create_failed"


def _write_goal(tmp_path: Path, *, beads: bool) -> Path:
    goal_path = tmp_path / "docs/goals/GOAL-SPEC-70.01.json"
    goal_path.parent.mkdir(parents=True)
    payload = json.loads(SOURCE_GOAL.read_text(encoding="utf-8"))
    routes = payload["blocked_routes"]
    for route in routes.values():
        route["also_create_beads_issue"] = beads
    goal_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return goal_path


def _last_goal_event(tmp_path: Path) -> dict[str, Any]:
    event_log = tmp_path / ".dp/goals/events.jsonl"
    lines = event_log.read_text(encoding="utf-8").splitlines()
    assert lines
    event = json.loads(lines[-1])
    assert isinstance(event, dict)
    return event
