from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main

SOURCE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"
VERBATIM = "I want dp doctor to tell me the truth about Beads health."
CONTRIBUTION = "Gives the root goal a deterministic health check surface."


def _write_goal(tmp_path: Path, *, with_intent: bool) -> None:
    goal = json.loads(SOURCE_GOAL.read_text(encoding="utf-8"))
    if with_intent:
        goal["intent"] = {
            "authorship": "agent_derived",
            "source": {"path": "docs/vision.md", "anchor": "doctor"},
            "verbatim": VERBATIM,
            "parent": {
                "goal": "GOAL-ROOT",
                "contribution": CONTRIBUTION,
                "residual": "Does not cover remote tracker divergence.",
            },
            "defeaters": ["Receipts stay green while real Beads state is broken."],
            "outcome_contact": {
                "signal": "Owner reports the doctor caught real state.",
                "channel": "docs/outcomes/doctor.md",
            },
        }
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs/vision.md").write_text("# Vision\n", encoding="utf-8")
    (tmp_path / "goal.json").write_text(json.dumps(goal), encoding="utf-8")


def _assert_reinjected(intent: dict[str, Any]) -> None:
    assert intent["verbatim"] == VERBATIM
    assert intent["source"]["path"] == "docs/vision.md"
    assert intent["source"]["anchor"] == "doctor"
    assert intent["parent_contribution"] == CONTRIBUTION


def test_goal_claim_reinjects_owner_words_verbatim(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, with_intent=True)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["goal", "claim", "goal.json", "--agent", "codex", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    _assert_reinjected(payload["intent"])


def test_goal_start_reinjects_owner_words_verbatim(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, with_intent=True)
    monkeypatch.chdir(tmp_path)
    assert main(["goal", "claim", "goal.json", "--agent", "codex", "--json"]) == 0
    capsys.readouterr()

    exit_code = main(["goal", "start", "goal.json", "--agent", "codex", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    _assert_reinjected(payload["intent"])


def test_goal_claim_omits_intent_when_goal_has_none(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, with_intent=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["goal", "claim", "goal.json", "--agent", "codex", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "intent" not in payload


def test_agent_launch_surfaces_intent_at_top_level(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, with_intent=True)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["agent", "launch", "--goal", "goal.json", "--supervised", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    _assert_reinjected(payload["intent"])
    _assert_reinjected(payload["claim"]["intent"])


def test_agent_bootstrap_surfaces_intent_for_the_claimed_goal(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, with_intent=True)
    (tmp_path / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["goal", "claim", "goal.json", "--agent", "codex", "--json"]) == 0
    capsys.readouterr()

    exit_code = main(["agent", "bootstrap", "--json", "--detail", "normal"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    lease = payload["result"]["goal_lease"]
    assert lease["goal_id"] == "GOAL-SPEC-70.01"
    _assert_reinjected(lease["intent"])


def test_agent_bootstrap_brief_puts_exact_owner_intent_before_workflow_actions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, with_intent=True)
    (tmp_path / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["goal", "claim", "goal.json", "--agent", "codex", "--json"]) == 0
    capsys.readouterr()

    exit_code = main(["agent", "bootstrap", "--json", "--detail", "brief"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert next(iter(payload["result"])) == "focus"
    focus = payload["result"]["focus"]
    assert focus["goal_id"] == "GOAL-SPEC-70.01"
    assert focus["stale"] is False
    _assert_reinjected(focus["intent"])
    assert payload["summary"].startswith("Owner intent is first in result.focus")
    assert output.index(focus["intent"]["verbatim"]) < output.index('"next_actions"')
    assert [action["id"] for action in payload["next_actions"]] == ["resume_goal"]
    assert len(output) <= 2_000
