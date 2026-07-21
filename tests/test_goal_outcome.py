from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main

SOURCE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"


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
    run_path.parent.mkdir(exist_ok=True)
    run_path.write_text(capsys.readouterr().out, encoding="utf-8")
    return run_path


def _status(capsys: Any) -> dict[str, Any]:
    assert main(["goal", "status", "goal.json", "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def _verify(run_path: Path, capsys: Any) -> dict[str, Any]:
    exit_code = main(
        ["goal", "verify", "goal.json", "--evidence", run_path.as_posix(), "--json"]
    )
    assert exit_code == 0
    return json.loads(capsys.readouterr().out)


def _outcome(outcome_class: str, capsys: Any, *, ref: str = "docs/outcomes/doctor.md#1") -> None:
    exit_code = main(
        ["goal", "outcome", "goal.json", "--class", outcome_class, "--ref", ref, "--json"]
    )
    assert exit_code == 0
    capsys.readouterr()


def test_goal_outcome_appends_event_and_resets_receipts_counter(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)

    assert _status(capsys)["receipts_since_last_outcome_contact"] is None

    _verify(run_path, capsys)
    status = _status(capsys)
    assert status["receipts_since_last_outcome_contact"] is None
    assert status["last_outcome"] is None

    exit_code = main(
        [
            "goal",
            "outcome",
            "goal.json",
            "--class",
            "useful",
            "--ref",
            "docs/outcomes/doctor.md#1",
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "goal.outcome"
    assert payload["outcome_class"] == "useful"
    assert payload["receipts_since_last_outcome_contact"] == 0
    assert payload["last_outcome"]["class"] == "useful"
    assert payload["last_outcome"]["ref"] == "docs/outcomes/doctor.md#1"
    assert payload["current_outcome"]["class"] == "useful"

    events = [
        json.loads(line)
        for line in (tmp_path / ".dp/goals/events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    outcome_events = [event for event in events if event["event"] == "outcome_contact"]
    assert len(outcome_events) == 1
    assert outcome_events[0]["class"] == "useful"
    assert outcome_events[0]["goal_sha256"].startswith("sha256:")

    _verify(run_path, capsys)
    status = _status(capsys)
    assert status["receipts_since_last_outcome_contact"] == 1
    assert status["last_outcome"]["class"] == "useful"


def test_goal_outcome_records_on_intent_less_minimal_goal(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Outcome recording is the zero-friction path: no full lint, only a parseable id.

    Historical goals that predate current lint levels (intent-less, no
    schema_version) must still accept outcome contact.
    """
    (tmp_path / "goal.json").write_text(
        json.dumps({"id": "GOAL-HISTORICAL"}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "goal",
            "outcome",
            "goal.json",
            "--class",
            "not_useful",
            "--ref",
            "docs/outcomes/log.md#7",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["goal_id"] == "GOAL-HISTORICAL"
    assert payload["last_outcome"]["class"] == "not_useful"

    events = [
        json.loads(line)
        for line in (tmp_path / ".dp/goals/events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["event"] for event in events] == ["outcome_contact"]
    assert events[0]["goal_id"] == "GOAL-HISTORICAL"
    assert events[0]["goal_sha256"].startswith("sha256:")


def test_goal_outcome_still_requires_a_parseable_goal_object(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    (tmp_path / "goal.json").write_text("not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["goal", "outcome", "goal.json", "--class", "useful", "--ref", "x", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "malformed_json"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_outcome_still_requires_a_goal_id(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    (tmp_path / "goal.json").write_text(json.dumps({"title": "no id"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["goal", "outcome", "goal.json", "--class", "useful", "--ref", "x", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "missing_id"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_outcome_rejects_unknown_class(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["goal", "outcome", "goal.json", "--class", "amazing", "--ref", "x", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "unknown_outcome_class"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_outcome_requires_non_empty_ref(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["goal", "outcome", "goal.json", "--class", "useful", "--ref", "  ", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "outcome_ref_required"
    assert not (tmp_path / ".dp/goals/events.jsonl").exists()


def test_goal_verify_reports_outcome_confirmed_separately_from_verified(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)

    payload = _verify(run_path, capsys)
    assert payload["evidence_status"] == "verified"
    assert payload["outcome_confirmed"] is False
    assert "verified" in payload["message"]
    assert "outcome" not in payload["message"].lower()

    _outcome("not_useful", capsys)
    payload = _verify(run_path, capsys)
    assert payload["outcome_confirmed"] is False

    _outcome("useful", capsys)
    payload = _verify(run_path, capsys)
    assert payload["outcome_confirmed"] is True

    _outcome("mixed", capsys, ref="docs/outcomes/doctor.md#2")
    payload = _verify(run_path, capsys)
    assert payload["outcome_confirmed"] is True


def test_goal_outcome_retraction_flips_confirmation_latest_wins(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A later not_useful on the unchanged goal retracts an earlier confirmation."""
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)

    _verify(run_path, capsys)
    _outcome("useful", capsys)
    assert _verify(run_path, capsys)["outcome_confirmed"] is True

    _outcome("not_useful", capsys, ref="docs/outcomes/doctor.md#2")
    payload = _verify(run_path, capsys)
    assert payload["outcome_confirmed"] is False

    status = _status(capsys)
    assert status["last_outcome"]["class"] == "not_useful"


def test_receipts_counter_counts_one_per_verify_cycle(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Only verified events are receipts; evidence_pending is not counted."""
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)

    _outcome("useful", capsys)
    assert _status(capsys)["receipts_since_last_outcome_contact"] == 0

    exit_code = main(
        ["goal", "complete", "goal.json", "--evidence", run_path.as_posix(), "--json"]
    )
    assert exit_code == 0
    capsys.readouterr()
    assert _status(capsys)["receipts_since_last_outcome_contact"] == 0

    _verify(run_path, capsys)
    assert _status(capsys)["receipts_since_last_outcome_contact"] == 1


def test_goal_verify_outcome_confirmation_expires_when_the_goal_changes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _write_verifiable_goal_and_plan(tmp_path)
    monkeypatch.chdir(tmp_path)
    run_path = _write_successful_evidence_run(capsys)

    _verify(run_path, capsys)
    _outcome("useful", capsys)
    assert _verify(run_path, capsys)["outcome_confirmed"] is True

    goal_payload = json.loads((tmp_path / "goal.json").read_text(encoding="utf-8"))
    goal_payload["title"] = "Make SPEC-70.01 true, plus remote checks"
    (tmp_path / "goal.json").write_text(json.dumps(goal_payload), encoding="utf-8")

    assert _verify(run_path, capsys)["outcome_confirmed"] is False
    assert _status(capsys)["current_outcome"] is None
