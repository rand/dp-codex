from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main

GOAL_FIXTURE_DIR = Path(__file__).parent / "fixtures/goals"


def test_campaign_recover_returns_resume_handoff_for_active_claim(
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
            "event": "claimed",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2098-01-01T00:00:00Z",
            "agent": "codex",
            "lease_expires_at": "2099-01-01T00:00:00Z",
        },
    )

    exit_code = main(["campaign", "recover", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    resume = payload["resume"]
    assert resume["action"] == "resume_claimed_goal"
    assert resume["goal_id"] == "GOAL-SPEC-70.01"
    assert resume["node_id"] == "first"
    assert resume["lease"]["holder"] == "codex"
    assert resume["commands"]["heartbeat"] == "dp goal heartbeat goals/one.json --json"
    assert resume["commands"]["campaign_run"] == (
        "dp campaign run campaign.json --driver codex --supervised --json"
    )
    assert resume["codex_goal"].startswith("/goal ")


def test_campaign_recover_treats_stale_claim_as_ready_work(
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
            "event": "claimed",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2000-01-01T00:00:00Z",
            "agent": "codex",
            "lease_expires_at": "2000-01-01T01:00:00Z",
        },
    )

    exit_code = main(["campaign", "recover", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    resume = payload["resume"]
    assert resume["action"] == "claim_next_goal"
    assert resume["goal_id"] == "GOAL-SPEC-70.01"
    assert resume["stale_claims"] == [
        {
            "node_id": "first",
            "goal_id": "GOAL-SPEC-70.01",
            "holder": "codex",
            "expires_at": "2000-01-01T01:00:00Z",
        }
    ]


def test_campaign_recover_routes_blocked_goal_to_blocker_resolution(
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
            "routing": {
                "ok": True,
                "action": "create_adr_stub",
                "artifact": {
                    "kind": "adr",
                    "path": "docs/adr/ADR-9999-blocker.md",
                    "reused": False,
                },
                "beads": {"requested": False, "ok": None, "issue_id": None},
            },
        },
    )

    exit_code = main(["campaign", "recover", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    resume = payload["resume"]
    assert resume["action"] == "resolve_blocker"
    assert resume["blocked"]["reason"] == "needs_decision"
    assert resume["blocked"]["routing"]["artifact"]["path"] == "docs/adr/ADR-9999-blocker.md"
    assert resume["commands"]["block"].endswith("--write-artifact --json")


def test_campaign_recover_routes_evidence_pending_to_verify_command(
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
            "event": "evidence_pending",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2026-01-01T00:00:00Z",
            "evidence": "runs/one.json",
        },
    )

    exit_code = main(["campaign", "recover", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    resume = payload["resume"]
    assert resume["action"] == "verify_evidence"
    assert resume["evidence"] == "runs/one.json"
    assert resume["commands"]["verify"] == (
        "dp verify --goal goals/one.json --evidence runs/one.json --json"
    )


def test_campaign_run_records_campaign_handoff_event(
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
    assert payload["campaign_event_log"] == ".dp/campaigns/events.jsonl"
    assert payload["campaign_event"]["event"] == "handoff_claimed"
    assert payload["campaign_event"]["goal_id"] == "GOAL-SPEC-70.01"

    events = _campaign_events(tmp_path)
    assert len(events) == 1
    assert events[0]["campaign_id"] == "CAMPAIGN-TMP"
    assert events[0]["loop_id"] == "LOOP-TMP"
    assert events[0]["node_id"] == "first"

    recover_exit = main(["campaign", "recover", campaign_path.as_posix(), "--json"])
    assert recover_exit == 0
    recover_payload = json.loads(capsys.readouterr().out)
    assert recover_payload["events"]["events_count"] == 1
    assert recover_payload["events"]["last_event"]["event"] == "handoff_claimed"


def test_campaign_run_resumes_active_claim_without_new_claim(
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
            "event": "claimed",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2098-01-01T00:00:00Z",
            "agent": "codex",
            "lease_expires_at": "2099-01-01T00:00:00Z",
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

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["message"] == "Existing claimed goal should be resumed."
    assert payload["next"]["command"] == "campaign.resume"
    assert payload["next"]["action"] == "resume_claimed_goal"
    assert payload["next"]["goal_id"] == "GOAL-SPEC-70.01"
    assert not (tmp_path / ".dp/campaigns/events.jsonl").exists()
    goal_events = _goal_events(tmp_path)
    assert [event["event"] for event in goal_events] == ["claimed"]


def _write_campaign_project(tmp_path: Path) -> Path:
    (tmp_path / "docs/primary").mkdir(parents=True)
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "goals").mkdir()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "loops").mkdir()

    (tmp_path / "docs/primary/spec.md").write_text("# Primary Spec\n", encoding="utf-8")
    (tmp_path / "docs/specs/SPEC-80-15.md").write_text("# SPEC-80.15\n", encoding="utf-8")
    (tmp_path / "docs/adr/ADR-0007.md").write_text("# ADR-0007\n", encoding="utf-8")
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
                        "beads_issue_id": "dpcx-pb5.12",
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
                    "specs": ["docs/specs/SPEC-80-15.md"],
                    "adrs": ["docs/adr/ADR-0007.md"],
                    "goals": ["goals/one.json", "goals/two.json"],
                    "evidence_plans": ["evidence/one.json", "evidence/two.json"],
                    "loops": ["loops/main.json"],
                    "beads_epics": ["dpcx-pb5"],
                    "beads_issues": ["dpcx-pb5.12"],
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


def _goal_events(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (tmp_path / ".dp/goals/events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _campaign_events(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (tmp_path / ".dp/campaigns/events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
