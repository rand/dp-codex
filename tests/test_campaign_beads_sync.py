from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Sequence

from dp.cli.main import main
from dp.providers.beads import CommandResult

GOAL_FIXTURE_DIR = Path(__file__).parent / "fixtures/goals"
EVIDENCE_FIXTURE_DIR = Path(__file__).parent / "fixtures/campaigns"


# @trace SPEC-80.18
def test_campaign_sync_beads_dry_run_plans_missing_dependency_without_mutation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    sync_module = importlib.import_module("dp.core.campaign_beads_sync")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        assert list(args) == ["dep", "list", "dpcx-goal-lint", "--json"]
        return CommandResult(returncode=0, stdout="[]\n", stderr="")

    monkeypatch.setattr(sync_module, "run_bd", fake_run_bd)

    exit_code = main(["campaign", "sync-beads", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["write"] is False
    assert payload["summary"] == {"planned": 1, "applied": 0, "skipped": 0, "failed": 0}
    assert payload["operations"] == [
        {
            "kind": "dependency",
            "action": "add",
            "issue_id": "dpcx-goal-lint",
            "depends_on_id": "dpcx-beads-doctor",
            "dependency_type": "blocks",
            "node_id": "goal-lint",
            "depends_on_node_id": "beads-doctor",
            "status": "planned",
            "command": [
                "dep",
                "add",
                "dpcx-goal-lint",
                "dpcx-beads-doctor",
                "--type",
                "blocks",
                "--json",
            ],
        }
    ]
    assert calls == [["dep", "list", "dpcx-goal-lint", "--json"]]


def test_campaign_sync_beads_write_adds_dependency_and_lifecycle_updates(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    _write_goal_events(
        tmp_path,
        [
            {
                "event": "claimed",
                "goal_id": "GOAL-SPEC-70.01",
                "goal_path": "docs/goals/GOAL-SPEC-70.01.json",
                "agent": "codex",
                "lease_expires_at": "2099-01-01T00:00:00Z",
            },
            {
                "event": "verified",
                "goal_id": "GOAL-SPEC-80.01-LINT",
                "goal_path": "docs/goals/GOAL-SPEC-80.01-LINT.json",
                "evidence": "docs/evidence-runs/RUN-GOAL-SPEC-80.01-LINT.json",
            },
        ],
    )
    monkeypatch.chdir(tmp_path)
    sync_module = importlib.import_module("dp.core.campaign_beads_sync")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        call = list(args)
        calls.append(call)
        if call == ["dep", "list", "dpcx-goal-lint", "--json"]:
            return CommandResult(returncode=0, stdout="[]\n", stderr="")
        return CommandResult(returncode=0, stdout='{"id":"ok"}\n', stderr="")

    monkeypatch.setattr(sync_module, "run_bd", fake_run_bd)

    exit_code = main(["campaign", "sync-beads", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["write"] is True
    assert payload["summary"] == {"planned": 0, "applied": 3, "skipped": 0, "failed": 0}
    assert [operation["status"] for operation in payload["operations"]] == [
        "applied",
        "applied",
        "applied",
    ]
    assert calls == [
        ["dep", "list", "dpcx-goal-lint", "--json"],
        [
            "dep",
            "add",
            "dpcx-goal-lint",
            "dpcx-beads-doctor",
            "--type",
            "blocks",
            "--json",
        ],
        [
            "update",
            "dpcx-beads-doctor",
            "--status",
            "in_progress",
            "--append-notes",
            "dp campaign sync-beads: goal GOAL-SPEC-70.01 is claimed.",
            "--json",
        ],
        [
            "close",
            "dpcx-goal-lint",
            "--reason",
            (
                "dp campaign sync-beads: goal GOAL-SPEC-80.01-LINT verified with "
                "evidence docs/evidence-runs/RUN-GOAL-SPEC-80.01-LINT.json."
            ),
            "--json",
        ],
    ]


def test_campaign_sync_beads_skips_existing_dependency(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    sync_module = importlib.import_module("dp.core.campaign_beads_sync")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "issue_id": "dpcx-goal-lint",
                        "depends_on_id": "dpcx-beads-doctor",
                        "type": "blocks",
                    }
                ]
            )
            + "\n",
            stderr="",
        )

    monkeypatch.setattr(sync_module, "run_bd", fake_run_bd)

    exit_code = main(["campaign", "sync-beads", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"] == {"planned": 0, "applied": 0, "skipped": 1, "failed": 0}
    assert payload["operations"][0]["status"] == "skipped"
    assert calls == [["dep", "list", "dpcx-goal-lint", "--json"]]


def test_campaign_sync_beads_blocked_and_released_states_update_notes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    _write_goal_events(
        tmp_path,
        [
            {
                "event": "blocked",
                "goal_id": "GOAL-SPEC-70.01",
                "goal_path": "docs/goals/GOAL-SPEC-70.01.json",
                "reason": "needs_decision",
                "routing": {
                    "beads": {
                        "requested": True,
                        "ok": True,
                        "issue_id": "dpcx-blocker",
                    }
                },
            },
            {
                "event": "released",
                "goal_id": "GOAL-SPEC-80.01-LINT",
                "goal_path": "docs/goals/GOAL-SPEC-80.01-LINT.json",
                "reason": "context reset",
            },
        ],
    )
    monkeypatch.chdir(tmp_path)
    sync_module = importlib.import_module("dp.core.campaign_beads_sync")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        call = list(args)
        calls.append(call)
        if call == ["dep", "list", "dpcx-goal-lint", "--json"]:
            return CommandResult(
                returncode=0,
                stdout=(
                    '[{"issue_id":"dpcx-goal-lint",'
                    '"depends_on_id":"dpcx-beads-doctor","type":"blocks"}]\n'
                ),
                stderr="",
            )
        if call == ["dep", "list", "dpcx-beads-doctor", "--json"]:
            return CommandResult(returncode=0, stdout="[]\n", stderr="")
        return CommandResult(returncode=0, stdout='{"id":"ok"}\n', stderr="")

    monkeypatch.setattr(sync_module, "run_bd", fake_run_bd)

    exit_code = main(["campaign", "sync-beads", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"] == {"planned": 0, "applied": 3, "skipped": 1, "failed": 0}
    assert calls == [
        ["dep", "list", "dpcx-beads-doctor", "--json"],
        [
            "dep",
            "add",
            "dpcx-beads-doctor",
            "dpcx-blocker",
            "--type",
            "blocks",
            "--json",
        ],
        ["dep", "list", "dpcx-goal-lint", "--json"],
        [
            "update",
            "dpcx-beads-doctor",
            "--status",
            "blocked",
            "--append-notes",
            "dp campaign sync-beads: goal GOAL-SPEC-70.01 blocked with reason needs_decision.",
            "--json",
        ],
        [
            "update",
            "dpcx-goal-lint",
            "--status",
            "open",
            "--append-notes",
            "dp campaign sync-beads: goal GOAL-SPEC-80.01-LINT released: context reset.",
            "--json",
        ],
    ]


def test_campaign_sync_beads_reports_beads_failure_without_continuing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    sync_module = importlib.import_module("dp.core.campaign_beads_sync")

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        if list(args) == ["dep", "list", "dpcx-goal-lint", "--json"]:
            return CommandResult(returncode=0, stdout="[]\n", stderr="")
        return CommandResult(returncode=1, stdout="", stderr="dependency failed")

    monkeypatch.setattr(sync_module, "run_bd", fake_run_bd)

    exit_code = main(["campaign", "sync-beads", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["summary"] == {"planned": 0, "applied": 0, "skipped": 0, "failed": 1}
    assert payload["operations"][0]["status"] == "failed"
    assert payload["operations"][0]["error"] == {
        "code": "beads_command_failed",
        "message": "dependency failed",
    }


def _write_campaign_project(tmp_path: Path) -> Path:
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "docs/adr").mkdir(parents=True)
    (tmp_path / "docs/goals").mkdir(parents=True)
    (tmp_path / "docs/evidence").mkdir(parents=True)
    (tmp_path / "docs/loops").mkdir(parents=True)
    (tmp_path / "docs/campaigns").mkdir(parents=True)
    (tmp_path / "docs/specs/SPEC-80-18-beads-lifecycle-synchronization.md").write_text(
        "# SPEC-80.18\n", encoding="utf-8"
    )
    (tmp_path / "docs/adr/ADR-0009-beads-sync-is-explicit-reconciliation.md").write_text(
        "# ADR-0009\n", encoding="utf-8"
    )

    _copy_json(
        GOAL_FIXTURE_DIR / "valid_spec_70_01.json",
        tmp_path / "docs/goals/GOAL-SPEC-70.01.json",
    )
    _copy_json(
        GOAL_FIXTURE_DIR / "valid_campaign_node.json",
        tmp_path / "docs/goals/GOAL-SPEC-80.01-LINT.json",
    )
    _copy_json(
        EVIDENCE_FIXTURE_DIR / "evidence_spec_70_01.json",
        tmp_path / "docs/evidence/EVIDENCE-SPEC-70.01.json",
    )
    _copy_json(
        EVIDENCE_FIXTURE_DIR / "evidence_spec_80_01.json",
        tmp_path / "docs/evidence/EVIDENCE-SPEC-80.01.json",
    )
    loop_path = tmp_path / "docs/loops/LOOP-SPEC-80.18.json"
    loop_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "LOOP-SPEC-80.18",
                "title": "SPEC-80.18 Beads sync loop",
                "nodes": [
                    {
                        "id": "beads-doctor",
                        "kind": "goal",
                        "goal_id": "GOAL-SPEC-70.01",
                        "goal_path": "docs/goals/GOAL-SPEC-70.01.json",
                        "beads_issue_id": "dpcx-beads-doctor",
                        "depends_on": [],
                        "evidence_plan": "docs/evidence/EVIDENCE-SPEC-70.01.json",
                    },
                    {
                        "id": "goal-lint",
                        "kind": "goal",
                        "goal_id": "GOAL-SPEC-80.01-LINT",
                        "goal_path": "docs/goals/GOAL-SPEC-80.01-LINT.json",
                        "beads_issue_id": "dpcx-goal-lint",
                        "depends_on": ["beads-doctor"],
                        "evidence_plan": "docs/evidence/EVIDENCE-SPEC-80.01.json",
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    campaign_path = tmp_path / "docs/campaigns/CAMPAIGN-SPEC-80.18.json"
    campaign_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "CAMPAIGN-SPEC-80.18",
                "title": "SPEC-80.18 Beads lifecycle sync",
                "primary_spec": {
                    "path": "docs/specs/SPEC-80-18-beads-lifecycle-synchronization.md",
                    "input_hash": "sha256:0123456789abcdef",
                },
                "artifacts": {
                    "specs": ["docs/specs/SPEC-80-18-beads-lifecycle-synchronization.md"],
                    "adrs": ["docs/adr/ADR-0009-beads-sync-is-explicit-reconciliation.md"],
                    "goals": [
                        "docs/goals/GOAL-SPEC-70.01.json",
                        "docs/goals/GOAL-SPEC-80.01-LINT.json",
                    ],
                    "evidence_plans": [
                        "docs/evidence/EVIDENCE-SPEC-70.01.json",
                        "docs/evidence/EVIDENCE-SPEC-80.01.json",
                    ],
                    "loops": [loop_path.relative_to(tmp_path).as_posix()],
                    "beads_epics": ["dpcx-pb5"],
                    "beads_issues": ["dpcx-beads-doctor", "dpcx-goal-lint"],
                },
                "state": {
                    "status": "active",
                    "current_loop": "LOOP-SPEC-80.18",
                    "current_goal": None,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return Path("docs/campaigns/CAMPAIGN-SPEC-80.18.json")


def _copy_json(source: Path, target: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_goal_events(tmp_path: Path, events: list[dict[str, Any]]) -> None:
    event_log = tmp_path / ".dp/goals/events.jsonl"
    event_log.parent.mkdir(parents=True)
    with event_log.open("w", encoding="utf-8") as stream:
        for index, event in enumerate(events, start=1):
            payload = {
                "schema_version": "0.1",
                "timestamp": f"2026-06-27T00:00:0{index}Z",
                **event,
            }
            stream.write(json.dumps(payload, sort_keys=True) + "\n")
