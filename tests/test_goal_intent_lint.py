from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dp.cli.main import main

BASE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"
INTENT_MARKER = "docs/reference/intent-graph.md"
SPEC81_SURFACE = (
    "docs/reference/agent-response-contract.md",
    "docs/reference/toolcards.md",
    "docs/reference/hint-codes.md",
)
ABSENT = object()


def _valid_root_intent() -> dict[str, Any]:
    return {
        "authorship": "owner",
        "source": {"path": "docs/vision.md", "anchor": "doctor"},
        "verbatim": "I want dp doctor to tell me the truth about Beads health.",
        "parent": None,
        "defeaters": [
            "Receipts stay green while the doctor misses a broken Beads daemon.",
        ],
        "outcome_contact": {
            "signal": "Owner runs dp doctor during a real session and it catches real state.",
            "channel": "docs/outcomes/doctor.md",
        },
    }


def _valid_child_intent() -> dict[str, Any]:
    intent = _valid_root_intent()
    intent["authorship"] = "agent_derived"
    intent["parent"] = {
        "goal": "GOAL-ROOT",
        "contribution": "Gives the root goal a deterministic health check surface.",
        "residual": "Does not cover remote tracker divergence.",
    }
    return intent


def _write_repo(
    tmp_path: Path,
    *,
    intent: Any,
    marker: bool,
    spec81_surface: bool | None = None,
) -> Path:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs/vision.md").write_text("# Vision\n", encoding="utf-8")
    if spec81_surface is None:
        spec81_surface = marker
    if spec81_surface:
        for surface in SPEC81_SURFACE:
            surface_path = tmp_path / surface
            surface_path.parent.mkdir(parents=True, exist_ok=True)
            surface_path.write_text("# Reference\n", encoding="utf-8")
    if marker:
        marker_path = tmp_path / INTENT_MARKER
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("# Intent Graph\n", encoding="utf-8")
    goal = json.loads(BASE_GOAL.read_text(encoding="utf-8"))
    if intent is not ABSENT:
        goal["intent"] = intent
    goal_path = tmp_path / "goal.json"
    goal_path.write_text(json.dumps(goal), encoding="utf-8")
    return goal_path


def _lint(capsys: Any) -> tuple[int, dict[str, Any]]:
    exit_code = main(["goal", "lint", "goal.json", "--json"])
    return exit_code, json.loads(capsys.readouterr().out)


def test_absent_intent_is_grandfathered_below_the_intent_graph_level(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_repo(tmp_path, intent=ABSENT, marker=False)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 0
    assert payload["valid"] is True


def test_absent_intent_is_rejected_at_the_intent_graph_level(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_repo(tmp_path, intent=ABSENT, marker=True)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 1
    assert payload["valid"] is False
    assert "missing_intent" in {error["code"] for error in payload["errors"]}


def test_marker_without_spec81_surface_does_not_enforce_intent(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Lint enforcement uses the adoption predicate: marker AND spec81 surface."""
    _write_repo(tmp_path, intent=ABSENT, marker=True, spec81_surface=False)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 0
    assert payload["valid"] is True


def test_valid_root_intent_passes_at_the_intent_graph_level(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_repo(tmp_path, intent=_valid_root_intent(), marker=True)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 0
    assert payload["valid"] is True


def test_valid_child_intent_passes_at_the_intent_graph_level(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_repo(tmp_path, intent=_valid_child_intent(), marker=True)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 0
    assert payload["valid"] is True


def _intent_mutations() -> list[tuple[str, dict[str, Any], str]]:
    cases: list[tuple[str, dict[str, Any], str]] = []

    intent = _valid_root_intent()
    intent["verbatim"] = "  "
    cases.append(("empty_verbatim", intent, "missing_intent_verbatim"))

    intent = _valid_root_intent()
    intent["authorship"] = "committee"
    cases.append(("bad_authorship", intent, "invalid_intent_authorship"))

    intent = _valid_root_intent()
    del intent["source"]
    cases.append(("missing_source", intent, "missing_intent_source"))

    intent = _valid_root_intent()
    intent["source"] = {"path": "docs/nonexistent.md"}
    cases.append(("source_not_in_repo", intent, "intent_source_not_found"))

    intent = _valid_root_intent()
    intent["source"] = {"path": "/etc/owner-notes.md"}
    cases.append(("absolute_source_path", intent, "invalid_intent_source_path"))

    intent = _valid_root_intent()
    intent["source"] = {"path": "docs"}
    cases.append(("directory_source_path", intent, "intent_source_not_a_file"))

    intent = _valid_root_intent()
    intent["source"] = {"path": "goal.json"}
    cases.append(("self_citing_source_path", intent, "intent_source_self_citation"))

    intent = _valid_root_intent()
    del intent["parent"]
    cases.append(("missing_parent_key", intent, "missing_intent_parent"))

    intent = _valid_root_intent()
    intent["authorship"] = "agent_derived"
    cases.append(("agent_derived_root", intent, "intent_root_requires_owner_authorship"))

    intent = _valid_child_intent()
    del intent["parent"]["contribution"]
    cases.append(("parent_without_contribution", intent, "invalid_intent_parent"))

    intent = _valid_child_intent()
    del intent["parent"]["residual"]
    cases.append(("parent_without_residual", intent, "invalid_intent_parent"))

    intent = _valid_root_intent()
    intent["defeaters"] = []
    cases.append(("empty_defeaters", intent, "missing_intent_defeaters"))

    intent = _valid_root_intent()
    intent["defeaters"] = [""]
    cases.append(("blank_defeater", intent, "invalid_intent_defeater"))

    intent = _valid_root_intent()
    del intent["outcome_contact"]
    cases.append(("missing_outcome_contact", intent, "missing_intent_outcome_contact"))

    intent = _valid_root_intent()
    intent["outcome_contact"] = {"signal": "Owner reaction recorded."}
    cases.append(("outcome_contact_without_channel", intent, "invalid_intent_outcome_contact"))

    return cases


@pytest.mark.parametrize(
    ("case_id", "intent", "expected_code"),
    _intent_mutations(),
    ids=[case_id for case_id, _, _ in _intent_mutations()],
)
def test_present_intent_is_validated_even_below_the_intent_graph_level(
    case_id: str,
    intent: dict[str, Any],
    expected_code: str,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_repo(tmp_path, intent=intent, marker=False)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 1
    assert payload["valid"] is False
    assert expected_code in {error["code"] for error in payload["errors"]}


def test_non_object_intent_is_rejected(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_repo(tmp_path, intent="serve the owner", marker=False)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _lint(capsys)

    assert exit_code == 1
    assert "invalid_intent" in {error["code"] for error in payload["errors"]}
