from __future__ import annotations

import json
from pathlib import Path

import pytest

from dp.cli.main import main

FIXTURE_DIR = Path("tests/fixtures/loops")
GOAL_FIXTURE_DIR = Path("tests/fixtures/goals")


def test_loop_lint_accepts_valid_fixture(capsys) -> None:
    exit_code = main(["loop", "lint", (FIXTURE_DIR / "valid_spec_80_04.json").as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["loop_id"] == "LOOP-SPEC-80.04"
    assert payload["errors"] == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_exit", "expected_code"),
    [
        ("invalid_cycle.json", 1, "dependency_cycle"),
        ("invalid_duplicate_node.json", 1, "duplicate_node_id"),
        ("invalid_missing_goal.json", 1, "invalid_goal_contract"),
        ("invalid_unknown_dependency.json", 1, "unknown_dependency"),
        ("invalid_unsupported_schema.json", 2, "unsupported_schema"),
    ],
)
def test_loop_lint_rejects_invalid_fixtures(
    fixture_name: str,
    expected_exit: int,
    expected_code: str,
    capsys,
) -> None:
    exit_code = main(["loop", "lint", (FIXTURE_DIR / fixture_name).as_posix(), "--json"])

    assert exit_code == expected_exit
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert expected_code in {error["code"] for error in payload["errors"]}


def test_loop_status_reports_ready_and_waiting_nodes(capsys) -> None:
    exit_code = main(
        ["loop", "status", (FIXTURE_DIR / "valid_spec_80_04.json").as_posix(), "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["ready_node_ids"] == ["beads-doctor"]
    assert payload["nodes"][0]["state"] == "ready"
    assert payload["nodes"][1]["state"] == "waiting"
    assert payload["nodes"][1]["unmet_dependencies"] == ["beads-doctor"]


def test_loop_next_claims_first_ready_node_and_emits_codex_package(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    loop_path = _write_loop_fixture(tmp_path, independent_second=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["loop", "next", loop_path.as_posix(), "--claim", "--emit", "codex", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "loop.next"
    assert payload["loop_id"] == "LOOP-TEST"
    assert payload["node_id"] == "first"
    assert payload["goal_id"] == "GOAL-SPEC-70.01"
    assert payload["beads_issue_id"] == "dpcx-66l"
    assert payload["lease"]["holder"] == "codex"
    assert payload["codex_goal"].startswith("/goal ")
    assert payload["read_first"] == [
        "docs/specs/SPEC-70-01-beads-doctor.md",
        "dp/providers/beads.py",
        "dp/cli/main.py",
    ]
    assert payload["evidence_plan"] == "docs/evidence/EVIDENCE-SPEC-70.01.json"
    assert payload["commands"]["start"] == "dp goal start goals/one.json --agent codex --json"
    assert payload["commands"]["evidence_run"] == (
        "dp evidence run docs/evidence/EVIDENCE-SPEC-70.01.json "
        "--output docs/evidence-runs/RUN-GOAL-SPEC-70.01.json --force --json"
    )
    assert payload["commands"]["complete"].endswith(
        "--evidence docs/evidence-runs/RUN-GOAL-SPEC-70.01.json --json"
    )
    assert (tmp_path / ".dp/goals/events.jsonl").exists()


def test_loop_next_skips_blocked_nodes(tmp_path: Path, monkeypatch, capsys) -> None:
    loop_path = _write_loop_fixture(tmp_path, independent_second=True)
    monkeypatch.chdir(tmp_path)
    _write_goal_event(
        tmp_path,
        {
            "schema_version": "0.1",
            "event": "blocked",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2026-01-01T00:00:00Z",
            "reason": "needs_decision",
        },
    )

    exit_code = main(["loop", "next", loop_path.as_posix(), "--emit", "codex", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["node_id"] == "second"
    assert payload["goal_id"] == "GOAL-SPEC-80.01-LINT"


def test_loop_next_waits_for_verified_dependencies(tmp_path: Path, monkeypatch, capsys) -> None:
    loop_path = _write_loop_fixture(tmp_path, independent_second=False)
    monkeypatch.chdir(tmp_path)

    first_exit = main(["loop", "next", loop_path.as_posix(), "--json"])
    assert first_exit == 0
    first_payload = json.loads(capsys.readouterr().out)
    assert first_payload["node_id"] == "first"

    _write_goal_event(
        tmp_path,
        {
            "schema_version": "0.1",
            "event": "verified",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2026-01-01T00:00:00Z",
            "evidence": "runs/one.json",
        },
    )

    second_exit = main(["loop", "next", loop_path.as_posix(), "--json"])

    assert second_exit == 0
    second_payload = json.loads(capsys.readouterr().out)
    assert second_payload["node_id"] == "second"


def test_loop_next_returns_no_ready_when_every_node_is_blocked(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    loop_path = _write_loop_fixture(tmp_path, independent_second=True)
    monkeypatch.chdir(tmp_path)
    _write_goal_event(
        tmp_path,
        {
            "schema_version": "0.1",
            "event": "blocked",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2026-01-01T00:00:00Z",
            "reason": "needs_decision",
        },
    )
    _write_goal_event(
        tmp_path,
        {
            "schema_version": "0.1",
            "event": "blocked",
            "goal_id": "GOAL-SPEC-80.01-LINT",
            "goal_path": "goals/two.json",
            "timestamp": "2026-01-01T00:00:00Z",
            "reason": "needs_validator",
        },
    )

    exit_code = main(["loop", "next", loop_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "no_ready_goal"


def _write_loop_fixture(tmp_path: Path, *, independent_second: bool) -> Path:
    goals_dir = tmp_path / "goals"
    goals_dir.mkdir()
    (goals_dir / "one.json").write_text(
        (GOAL_FIXTURE_DIR / "valid_spec_70_01.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (goals_dir / "two.json").write_text(
        (GOAL_FIXTURE_DIR / "valid_campaign_node.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    loop = {
        "schema_version": "0.1",
        "id": "LOOP-TEST",
        "title": "Loop test",
        "nodes": [
            {
                "id": "first",
                "goal_id": "GOAL-SPEC-70.01",
                "goal_path": "goals/one.json",
                "beads_issue_id": "dpcx-66l",
                "depends_on": [],
                "evidence_plan": "docs/evidence/EVIDENCE-SPEC-70.01.json",
            },
            {
                "id": "second",
                "goal_id": "GOAL-SPEC-80.01-LINT",
                "goal_path": "goals/two.json",
                "beads_issue_id": "dpcx-pb5.1",
                "depends_on": [] if independent_second else ["first"],
                "evidence_plan": "docs/evidence/EVIDENCE-SPEC-80.01.json",
            },
        ],
    }
    loop_path = tmp_path / "loop.json"
    loop_path.write_text(json.dumps(loop), encoding="utf-8")
    return loop_path


def _write_goal_event(tmp_path: Path, event: dict[str, object]) -> None:
    event_log = tmp_path / ".dp/goals/events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True))
        stream.write("\n")
