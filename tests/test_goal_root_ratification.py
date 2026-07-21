from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dp.cli.main import main
from dp.core.hints import explain_code
from dp.core.intent_graph import goal_file_digest

BASE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"


def _root_intent(authorship: str) -> dict[str, Any]:
    return {
        "authorship": authorship,
        "source": {"path": "docs/vision.md"},
        "verbatim": "Local-first agents should serve stated owner outcomes.",
        "parent": None,
        "defeaters": [
            "Receipts stay green while the owner outcome never materializes.",
        ],
        "outcome_contact": {
            "signal": "Owner records a reaction after real use.",
            "channel": "docs/outcomes/log.md",
        },
    }


def _write_goal(tmp_path: Path, *, authorship: str) -> Path:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs/vision.md").write_text("# Vision\n", encoding="utf-8")
    goal = json.loads(BASE_GOAL.read_text(encoding="utf-8"))
    goal["intent"] = _root_intent(authorship)
    goal_path = tmp_path / "goal.json"
    goal_path.write_text(json.dumps(goal), encoding="utf-8")
    return goal_path


@pytest.mark.parametrize(
    "argv",
    [
        ["goal", "claim", "goal.json", "--agent", "codex", "--json"],
        ["goal", "start", "goal.json", "--agent", "codex", "--json"],
    ],
    ids=["claim", "start"],
)
def test_claim_and_start_refuse_unratified_agent_root(
    argv: list[str],
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """An agent-proposed root lints clean but cannot be pursued until ratified."""
    _write_goal(tmp_path, authorship="agent_derived")
    monkeypatch.chdir(tmp_path)

    exit_code = main(argv)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "unratified_root_goal"
    assert "owner ratification" in payload["error"]["message"]
    assert "owner_ratified" in payload["error"]["message"]
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


@pytest.mark.parametrize("authorship", ["owner", "owner_ratified"])
def test_claim_and_start_proceed_once_the_root_is_ratified(
    authorship: str,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_goal(tmp_path, authorship=authorship)
    monkeypatch.chdir(tmp_path)

    claim_exit = main(["goal", "claim", "goal.json", "--agent", "codex", "--json"])
    claim_payload = json.loads(capsys.readouterr().out)
    assert claim_exit == 0
    assert claim_payload["ok"] is True
    assert claim_payload["state"] == "claimed"

    start_exit = main(["goal", "start", "goal.json", "--agent", "codex", "--json"])
    start_payload = json.loads(capsys.readouterr().out)
    assert start_exit == 0
    assert start_payload["state"] == "started"


def test_ratifying_the_goal_file_unblocks_a_previous_refusal(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, authorship="agent_derived")
    monkeypatch.chdir(tmp_path)

    assert main(["goal", "claim", "goal.json", "--agent", "codex", "--json"]) == 1
    capsys.readouterr()

    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    goal["intent"]["authorship"] = "owner_ratified"
    goal_path.write_text(json.dumps(goal), encoding="utf-8")

    exit_code = main(["goal", "claim", "goal.json", "--agent", "codex", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["state"] == "claimed"


def test_unratified_root_goal_error_code_is_explained() -> None:
    payload, exit_code = explain_code("unratified_root_goal")

    assert exit_code == 0
    assert payload["code"] == "unratified_root_goal"
    assert "owner_ratified" in payload["summary"]
    assert any("dp goal ratify" in action["command"] for action in payload["next_actions"])


def _read_events(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (tmp_path / ".dp/goals/events.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_ratify_flips_authorship_appends_event_and_unblocks_claim(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, authorship="agent_derived")
    before = json.loads(goal_path.read_text(encoding="utf-8"))
    monkeypatch.chdir(tmp_path)

    exit_code = main(["goal", "ratify", "goal.json", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["command"] == "goal.ratify"
    assert payload["authorship"] == "owner_ratified"

    after = json.loads(goal_path.read_text(encoding="utf-8"))
    assert after["intent"]["authorship"] == "owner_ratified"
    # The exact single-field mutation: everything else is untouched.
    before["intent"]["authorship"] = "owner_ratified"
    assert after == before

    ratified_events = [event for event in _read_events(tmp_path) if event["event"] == "ratified"]
    assert len(ratified_events) == 1
    assert ratified_events[0]["goal_id"] == after["id"]
    assert ratified_events[0]["goal_sha256"] == payload["goal_sha256"]
    assert ratified_events[0]["goal_sha256"] == goal_file_digest(goal_path)

    claim_exit = main(["goal", "claim", "goal.json", "--agent", "codex", "--json"])
    claim_payload = json.loads(capsys.readouterr().out)
    assert claim_exit == 0
    assert claim_payload["state"] == "claimed"


def test_ratify_refuses_an_already_ratified_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, authorship="owner_ratified")
    original = goal_path.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["goal", "ratify", "goal.json", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_agent_proposed_root"
    assert goal_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_ratify_refuses_a_non_root_goal(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goal_path = _write_goal(tmp_path, authorship="agent_derived")
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    goal["intent"]["parent"] = {
        "goal": "GOAL-ROOT",
        "contribution": "Serves the root outcome.",
    }
    goal_path.write_text(json.dumps(goal), encoding="utf-8")
    original = goal_path.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["goal", "ratify", "goal.json", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["error"]["code"] == "not_agent_proposed_root"
    assert goal_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()
