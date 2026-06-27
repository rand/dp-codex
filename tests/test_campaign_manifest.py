from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate

from dp.cli.main import main

FIXTURE_DIR = Path("tests/fixtures/campaigns")
GOAL_FIXTURE_DIR = Path("tests/fixtures/goals")


def test_campaign_lint_accepts_valid_fixture(capsys) -> None:
    exit_code = main(
        ["campaign", "lint", (FIXTURE_DIR / "valid_spec_80_06.json").as_posix(), "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["campaign_id"] == "CAMPAIGN-SPEC-80.06"
    assert payload["errors"] == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_exit", "expected_code"),
    [
        ("invalid_unsupported_schema.json", 2, "unsupported_schema"),
        ("invalid_missing_loop_artifact.json", 1, "missing_artifact"),
        ("invalid_duplicate_artifact.json", 1, "duplicate_artifact"),
        ("invalid_loop_goal_not_declared.json", 1, "loop_goal_not_declared"),
    ],
)
def test_campaign_lint_rejects_invalid_fixtures(
    fixture_name: str,
    expected_exit: int,
    expected_code: str,
    capsys,
) -> None:
    exit_code = main(["campaign", "lint", (FIXTURE_DIR / fixture_name).as_posix(), "--json"])

    assert exit_code == expected_exit
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert expected_code in {error["code"] for error in payload["errors"]}


def test_campaign_lint_json_output_matches_schema(capsys) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-lint-output.schema.json").read_text(encoding="utf-8")
    )

    exit_code = main(
        ["campaign", "lint", (FIXTURE_DIR / "valid_spec_80_06.json").as_posix(), "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_status_reports_incomplete_campaign(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "status", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "campaign.status"
    assert payload["campaign_id"] == "CAMPAIGN-TMP"
    assert payload["derived_status"] == "active"
    assert payload["summary"]["goals"] == 2
    assert payload["summary"]["ready_goals"] == 1
    assert payload["summary"]["waiting_goals"] == 1
    assert payload["loop"]["ready_node_ids"] == ["first"]


def test_campaign_recover_reports_blocked_campaign(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
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

    exit_code = main(["campaign", "recover", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["recoverable"] is True
    assert payload["status"]["derived_status"] == "blocked"
    assert payload["status"]["loop"]["blocked_node_ids"] == ["first"]
    assert payload["missing_artifacts"] == []


def test_campaign_recover_reports_missing_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path, missing_loop=True)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "recover", campaign_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["recoverable"] is False
    assert payload["campaign_id"] == "CAMPAIGN-TMP"
    assert payload["missing_artifacts"] == ["loops/missing.json"]
    assert payload["lint"]["valid"] is False


def _write_campaign_project(tmp_path: Path, *, missing_loop: bool = False) -> Path:
    (tmp_path / "docs/primary").mkdir(parents=True)
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "goals").mkdir()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "loops").mkdir()

    (tmp_path / "docs/primary/spec.md").write_text("# Primary Spec\n", encoding="utf-8")
    (tmp_path / "docs/specs/SPEC-80-06.md").write_text("# SPEC-80.06\n", encoding="utf-8")
    (tmp_path / "docs/adr/ADR-0005.md").write_text("# ADR-0005\n", encoding="utf-8")
    (tmp_path / "goals/one.json").write_text(
        (GOAL_FIXTURE_DIR / "valid_spec_70_01.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "goals/two.json").write_text(
        (GOAL_FIXTURE_DIR / "valid_campaign_node.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "evidence/one.json").write_text(
        _evidence_plan("EVIDENCE-TMP-ONE", "GOAL-SPEC-70.01"),
        encoding="utf-8",
    )
    (tmp_path / "evidence/two.json").write_text(
        _evidence_plan("EVIDENCE-TMP-TWO", "GOAL-SPEC-80.01-LINT"),
        encoding="utf-8",
    )
    if not missing_loop:
        (tmp_path / "loops/main.json").write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "id": "LOOP-TMP",
                    "title": "Temporary loop",
                    "nodes": [
                        {
                            "id": "first",
                            "kind": "goal",
                            "goal_id": "GOAL-SPEC-70.01",
                            "goal_path": "goals/one.json",
                            "depends_on": [],
                            "evidence_plan": "evidence/one.json",
                        },
                        {
                            "id": "second",
                            "kind": "goal",
                            "goal_id": "GOAL-SPEC-80.01-LINT",
                            "goal_path": "goals/two.json",
                            "depends_on": ["first"],
                            "evidence_plan": "evidence/two.json",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    loop_path = "loops/missing.json" if missing_loop else "loops/main.json"
    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "CAMPAIGN-TMP",
                "title": "Temporary campaign",
                "primary_spec": {"path": "docs/primary/spec.md"},
                "artifacts": {
                    "specs": ["docs/specs/SPEC-80-06.md"],
                    "adrs": ["docs/adr/ADR-0005.md"],
                    "goals": ["goals/one.json", "goals/two.json"],
                    "evidence_plans": ["evidence/one.json", "evidence/two.json"],
                    "loops": [loop_path],
                    "beads_epics": ["dpcx-pb5"],
                    "beads_issues": ["dpcx-pb5.6"],
                },
                "state": {
                    "status": "active",
                    "current_loop": "LOOP-TMP",
                    "current_goal": None,
                },
            }
        ),
        encoding="utf-8",
    )
    return Path("campaign.json")


def _evidence_plan(evidence_id: str, goal_id: str) -> str:
    return json.dumps(
        {
            "schema_version": "0.1",
            "id": evidence_id,
            "goal_id": goal_id,
            "checks": [
                {
                    "id": "doctor",
                    "kind": "registered_command",
                    "argv": ["dp", "doctor", "--json"],
                    "timeout_seconds": 30,
                    "success_exit_codes": [0],
                    "assertions": [{"type": "stdout_json"}],
                    "mutation_policy": "read_only",
                }
            ],
        }
    )


def _write_goal_event(tmp_path: Path, event: dict[str, object]) -> None:
    event_log = tmp_path / ".dp/goals/events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True))
        stream.write("\n")
