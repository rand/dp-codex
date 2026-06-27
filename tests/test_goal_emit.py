from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

VALID_GOAL = Path("tests/fixtures/goals/valid_spec_70_01.json")


def test_goal_emit_codex_returns_operable_prompt(capsys) -> None:
    exit_code = main(["goal", "emit", VALID_GOAL.as_posix(), "--format", "codex", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["goal_id"] == "GOAL-SPEC-70.01"
    assert payload["codex_goal"].startswith("/goal ")
    assert "dp goal start tests/fixtures/goals/valid_spec_70_01.json --agent codex --json" in (
        payload["codex_goal"]
    )
    assert "dp goal block tests/fixtures/goals/valid_spec_70_01.json --reason <reason> --json" in (
        payload["codex_goal"]
    )
    assert "Never claim completion from narration" in payload["codex_goal"]
    assert payload["commands"]["complete"].endswith("--evidence <run.json> --json")
    assert payload["commands"]["verify"].endswith("--evidence <run.json> --json")
    assert "dp goal verify tests/fixtures/goals/valid_spec_70_01.json --evidence <run.json>" in (
        payload["codex_goal"]
    )


def test_agent_prompt_delegates_to_goal_emit(capsys) -> None:
    exit_code = main(
        ["agent", "prompt", "--goal", VALID_GOAL.as_posix(), "--format", "codex", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "agent.prompt"
    assert payload["goal_id"] == "GOAL-SPEC-70.01"
    assert "Start the goal through dp" in payload["codex_goal"]
