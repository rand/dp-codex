from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

GOAL_FIXTURE_DIR = Path("tests/fixtures/goals")


def test_campaign_run_supervised_claims_one_goal_and_emits_codex_package(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
            "--driver",
            "codex",
            "--supervised",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "campaign.run"
    assert payload["mode"] == "supervised_once"
    assert payload["driver"] == "codex"
    assert payload["supervised"] is True
    assert payload["autonomous"] is False
    assert payload["launched"] is False
    assert payload["campaign_id"] == "CAMPAIGN-TMP"
    assert payload["next"]["command"] == "loop.next"
    assert payload["next"]["goal_id"] == "GOAL-SPEC-70.01"
    assert payload["next"]["codex_goal"].startswith("/goal ")
    assert payload["next"]["commands"]["start"] == (
        "dp goal start goals/one.json --agent codex --json"
    )
    assert payload["stop_conditions"]

    event_log = tmp_path / ".dp/goals/events.jsonl"
    events = [
        json.loads(line)
        for line in event_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    claim_events = [event for event in events if event["event"] == "claimed"]
    assert len(claim_events) == 1
    assert claim_events[0]["goal_id"] == "GOAL-SPEC-70.01"


def test_campaign_run_requires_supervised_flag(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "run", campaign_path.as_posix(), "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "supervised_required"


def test_campaign_run_rejects_unsupported_driver(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
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


def test_campaign_run_reports_no_ready_work_without_launching(
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

    exit_code = main(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
            "--driver",
            "codex",
            "--supervised",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["launched"] is False
    assert payload["next"]["error"]["code"] == "no_ready_goal"


def _write_campaign_project(tmp_path: Path) -> Path:
    (tmp_path / "docs/primary").mkdir(parents=True)
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "goals").mkdir()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "loops").mkdir()

    (tmp_path / "docs/primary/spec.md").write_text("# Primary Spec\n", encoding="utf-8")
    (tmp_path / "docs/specs/SPEC-80-13.md").write_text("# SPEC-80.13\n", encoding="utf-8")
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

    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "CAMPAIGN-TMP",
                "title": "Temporary campaign",
                "primary_spec": {"path": "docs/primary/spec.md"},
                "artifacts": {
                    "specs": ["docs/specs/SPEC-80-13.md"],
                    "adrs": ["docs/adr/ADR-0005.md"],
                    "goals": ["goals/one.json", "goals/two.json"],
                    "evidence_plans": ["evidence/one.json", "evidence/two.json"],
                    "loops": ["loops/main.json"],
                    "beads_epics": ["dpcx-pb5"],
                    "beads_issues": ["dpcx-pb5.9.4"],
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
