from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

GOAL_FIXTURE = Path("tests/fixtures/goals/valid_spec_70_01.json")


def test_agent_launch_claims_starts_and_emits_codex_package(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = tmp_path / "goal.json"
    goal_path.write_text(GOAL_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "agent",
            "launch",
            "--goal",
            "goal.json",
            "--driver",
            "codex",
            "--agent",
            "codex",
            "--lease",
            "2h",
            "--supervised",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "agent.launch"
    assert payload["driver"] == "codex"
    assert payload["supervised"] is True
    assert payload["launched"] is False
    assert payload["goal_id"] == "GOAL-SPEC-70.01"
    assert payload["codex_goal"].startswith("/goal ")
    assert payload["claim"]["command"] == "goal.claim"
    assert payload["start"]["command"] == "goal.start"

    events = [
        json.loads(line)
        for line in Path(".dp/goals/events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event"] for event in events] == ["claimed", "started"]


def test_agent_launch_requires_supervised_flag(capsys) -> None:
    exit_code = main(
        [
            "agent",
            "launch",
            "--goal",
            GOAL_FIXTURE.as_posix(),
            "--driver",
            "codex",
            "--json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "supervised_required"


def test_agent_launch_rejects_unsupported_driver(capsys) -> None:
    exit_code = main(
        [
            "agent",
            "launch",
            "--goal",
            GOAL_FIXTURE.as_posix(),
            "--driver",
            "autobot",
            "--supervised",
            "--json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "unsupported_driver"
