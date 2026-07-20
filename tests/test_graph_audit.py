from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main
from dp.core.intent_graph import goal_file_digest

STALE_DIGEST = "sha256:" + "0" * 64


def _intent(
    *,
    parent: Any = None,
    defeaters: list[str] | None = None,
    authorship: str = "owner",
) -> dict[str, Any]:
    return {
        "authorship": authorship,
        "source": {"path": "docs/vision.md"},
        "verbatim": "Local-first agents should serve stated owner outcomes.",
        "parent": parent,
        "defeaters": (
            defeaters
            if defeaters is not None
            else ["Receipts stay green while the owner outcome never materializes."]
        ),
        "outcome_contact": {
            "signal": "Owner records a reaction after real use.",
            "channel": "docs/outcomes/log.md",
        },
    }


def _write_goal(tmp_path: Path, name: str, payload: dict[str, Any]) -> Path:
    path = tmp_path / "docs/goals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_fixture_tree(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs/vision.md").write_text("# Vision\n", encoding="utf-8")

    root_path = _write_goal(
        tmp_path,
        "GOAL-ROOT.json",
        {"schema_version": "0.1", "id": "GOAL-ROOT", "intent": _intent()},
    )
    root_digest = goal_file_digest(root_path)

    _write_goal(
        tmp_path,
        "GOAL-CHILD.json",
        {
            "schema_version": "0.1",
            "id": "GOAL-CHILD",
            "intent": _intent(
                authorship="agent_derived",
                parent={
                    "goal": "GOAL-ROOT",
                    "contribution": "Delivers the root outcome's first slice.",
                    "residual": "Does not cover the root's replay requirements.",
                    "parent_snapshot": root_digest,
                },
            ),
        },
    )
    _write_goal(
        tmp_path,
        "GOAL-STALE.json",
        {
            "schema_version": "0.1",
            "id": "GOAL-STALE",
            "intent": _intent(
                authorship="agent_derived",
                parent={
                    "goal": "GOAL-ROOT",
                    "contribution": "Serves the root outcome.",
                    "residual": "Unknown residual.",
                    "parent_snapshot": STALE_DIGEST,
                },
            ),
        },
    )
    _write_goal(
        tmp_path,
        "GOAL-ORPHAN.json",
        {
            "schema_version": "0.1",
            "id": "GOAL-ORPHAN",
            "intent": _intent(
                authorship="agent_derived",
                parent={
                    "goal": "GOAL-NOPE",
                    "contribution": "Claims to serve a parent that has no file.",
                    "residual": "All of it.",
                },
            ),
        },
    )
    _write_goal(
        tmp_path,
        "GOAL-NOINTENT.json",
        {"schema_version": "0.1", "id": "GOAL-NOINTENT"},
    )
    _write_goal(
        tmp_path,
        "GOAL-EMPTYDEF.json",
        {
            "schema_version": "0.1",
            "id": "GOAL-EMPTYDEF",
            "intent": _intent(defeaters=[]),
        },
    )

    event_log = tmp_path / ".dp/goals/events.jsonl"
    event_log.parent.mkdir(parents=True)
    events = [
        {
            "schema_version": "0.1",
            "event": "outcome_contact",
            "goal_id": "GOAL-ROOT",
            "goal_path": "docs/goals/GOAL-ROOT.json",
            "timestamp": "2026-07-19T00:00:00Z",
            "class": "useful",
            "ref": "docs/outcomes/log.md#1",
        },
        {
            "schema_version": "0.1",
            "event": "verified",
            "goal_id": "GOAL-ROOT",
            "goal_path": "docs/goals/GOAL-ROOT.json",
            "timestamp": "2026-07-20T00:00:00Z",
        },
    ]
    event_log.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def _audit(capsys: Any) -> tuple[int, dict[str, Any]]:
    exit_code = main(["graph", "audit", "--json"])
    return exit_code, json.loads(capsys.readouterr().out)


def test_graph_audit_reports_findings_without_gating(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_fixture_tree(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _audit(capsys)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["command"] == "graph.audit"
    assert payload["summary"]["goals"] == 6

    codes_by_goal = {
        goal["goal_id"]: set(goal["findings"]) for goal in payload["goals"]
    }
    assert codes_by_goal["GOAL-ROOT"] == set()
    assert codes_by_goal["GOAL-CHILD"] == set()
    assert codes_by_goal["GOAL-NOINTENT"] == {"missing_intent"}
    assert codes_by_goal["GOAL-EMPTYDEF"] == {"empty_defeaters"}
    assert codes_by_goal["GOAL-ORPHAN"] == {"unknown_parent_goal"}
    assert codes_by_goal["GOAL-STALE"] == {"stale_parent_snapshot"}

    flat_codes = {finding["code"] for finding in payload["findings"]}
    assert flat_codes == {
        "missing_intent",
        "empty_defeaters",
        "unknown_parent_goal",
        "stale_parent_snapshot",
    }


def test_graph_audit_reports_receipts_since_last_outcome_contact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_fixture_tree(tmp_path)
    monkeypatch.chdir(tmp_path)

    _, payload = _audit(capsys)

    by_goal = {goal["goal_id"]: goal for goal in payload["goals"]}
    assert by_goal["GOAL-ROOT"]["receipts_since_last_outcome_contact"] == 1
    assert by_goal["GOAL-ROOT"]["last_outcome_class"] == "useful"
    assert by_goal["GOAL-CHILD"]["receipts_since_last_outcome_contact"] is None
    assert by_goal["GOAL-CHILD"]["last_outcome_class"] is None
    assert by_goal["GOAL-CHILD"]["parent"] == "GOAL-ROOT"


def test_graph_audit_flags_partial_intent_blocks(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/vision.md").write_text("# Vision\n", encoding="utf-8")
    broken_intent = _intent()
    broken_intent["verbatim"] = ""
    _write_goal(
        tmp_path,
        "GOAL-PARTIAL.json",
        {"schema_version": "0.1", "id": "GOAL-PARTIAL", "intent": broken_intent},
    )
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _audit(capsys)

    assert exit_code == 0
    finding = next(f for f in payload["findings"] if f["code"] == "partial_intent")
    assert finding["goal_id"] == "GOAL-PARTIAL"
    assert "missing_intent_verbatim" in finding["detail"]


def test_graph_audit_handles_malformed_and_missing_goals(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    goals_dir = tmp_path / "docs/goals"
    goals_dir.mkdir(parents=True)
    (goals_dir / "broken.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _audit(capsys)

    assert exit_code == 0
    assert {finding["code"] for finding in payload["findings"]} == {"malformed_goal"}


def test_graph_audit_on_empty_repo_reports_no_goals(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code, payload = _audit(capsys)

    assert exit_code == 0
    assert payload["summary"] == {"goals": 0, "findings": 0, "with_intent": 0}
