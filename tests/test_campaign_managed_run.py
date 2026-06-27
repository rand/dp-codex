from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

GOAL_FIXTURE_DIR = Path("tests/fixtures/goals")


def test_campaign_managed_run_claims_one_ready_goal_and_stops(
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
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["mode"] == "managed_supervised"
    assert payload["stop_reason"] == "handoff_claimed"
    assert payload["iterations"][0]["action"] == "claim_next_goal"
    assert payload["next"]["command"] == "loop.next"
    assert payload["next"]["goal_id"] == "GOAL-SPEC-70.01"
    assert payload["launched"] is False
    assert payload["autonomous"] is False

    events = _goal_events(tmp_path)
    claim_events = [event for event in events if event["event"] == "claimed"]
    assert len(claim_events) == 1


def test_campaign_managed_run_stops_on_stale_lease_without_claiming(
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

    exit_code = main(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
            "--driver",
            "codex",
            "--supervised",
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_reason"] == "stale_lease"
    assert payload["resume"]["stale_claims"][0]["goal_id"] == "GOAL-SPEC-70.01"
    assert len([event for event in _goal_events(tmp_path) if event["event"] == "claimed"]) == 1


def test_campaign_managed_run_resumes_active_claim(
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
            "timestamp": "2026-01-01T00:00:00Z",
            "agent": "codex",
            "lease_expires_at": "2999-01-01T00:00:00Z",
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
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_reason"] == "active_claim"
    assert payload["next"]["action"] == "resume_claimed_goal"
    assert len([event for event in _goal_events(tmp_path) if event["event"] == "claimed"]) == 1


def test_campaign_managed_run_stops_on_evidence_pending(
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
            "evidence": "docs/evidence-runs/RUN-GOAL-SPEC-70.01.json",
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
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_reason"] == "evidence_pending"
    assert payload["next"]["action"] == "verify_evidence"
    assert not [event for event in _goal_events(tmp_path) if event["event"] == "claimed"]


def test_campaign_managed_run_stops_on_blocker(
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
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_reason"] == "blocked"
    assert payload["next"]["action"] == "resolve_blocker"
    assert payload["launched"] is False


def test_campaign_managed_run_reports_verified_loop(
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
            "event": "verified",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "timestamp": "2026-01-01T00:00:00Z",
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
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_reason"] == "campaign_verified"
    assert payload["next"]["action"] == "campaign_verified"
    assert payload["ok"] is True


def test_campaign_managed_run_rejects_draft_campaign(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path, status="draft")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
            "--driver",
            "codex",
            "--supervised",
            "--managed",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_reason"] == "campaign_not_ready"
    assert payload["error"]["code"] == "campaign_not_ready"


def test_campaign_managed_run_rejects_invalid_max_steps(
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
            "--managed",
            "--max-steps",
            "0",
            "--json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["stop_conditions"]
    assert payload["error"]["code"] == "invalid_max_steps"
    assert payload["mode"] == "managed_supervised"


def _write_campaign_project(tmp_path: Path, *, status: str = "ready") -> Path:
    (tmp_path / "docs/primary").mkdir(parents=True)
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "goals").mkdir()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "loops").mkdir()

    (tmp_path / "docs/primary/spec.md").write_text("# Primary Spec\n", encoding="utf-8")
    (tmp_path / "docs/specs/SPEC-80-20.md").write_text("# SPEC-80.20\n", encoding="utf-8")
    (tmp_path / "docs/adr/ADR-0011.md").write_text("# ADR-0011\n", encoding="utf-8")
    (tmp_path / "goals/one.json").write_text(
        (GOAL_FIXTURE_DIR / "valid_spec_70_01.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "evidence/one.json").write_text(
        _evidence_plan("EVIDENCE-TMP-ONE", "GOAL-SPEC-70.01"),
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
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "campaign.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "CAMPAIGN-TMP",
                "title": "Temporary campaign",
                "primary_spec": {"path": "docs/primary/spec.md"},
                "artifacts": {
                    "specs": ["docs/specs/SPEC-80-20.md"],
                    "adrs": ["docs/adr/ADR-0011.md"],
                    "goals": ["goals/one.json"],
                    "evidence_plans": ["evidence/one.json"],
                    "loops": ["loops/main.json"],
                    "beads_epics": ["dpcx-pb5"],
                    "beads_issues": ["dpcx-pb5.17"],
                },
                "state": {
                    "status": status,
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


def _goal_events(tmp_path: Path) -> list[dict[str, object]]:
    event_log = tmp_path / ".dp/goals/events.jsonl"
    if not event_log.exists():
        return []
    return [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
