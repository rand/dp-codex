from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Sequence

from dp.cli.main import main
from dp.providers.beads import CommandResult

FIELD_REPORT_SPEC = Path("tests/fixtures/primary_specs/field_report_cli.md")


# @trace SPEC-80.19
def test_spec80_field_report_campaign_pilot(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_fixture(tmp_path, FIELD_REPORT_SPEC, "docs/primary/field-report-cli.md")
    monkeypatch.chdir(tmp_path)
    beads_calls = _install_fake_beads(monkeypatch)

    init_payload = _run_json(
        [
            "campaign",
            "init",
            "--primary-spec",
            primary_spec.as_posix(),
            "--write",
            "--json",
        ],
        capsys,
    )
    campaign_path = Path(init_payload["artifacts"]["campaign"])
    loop_path = Path(init_payload["artifacts"]["loop"])

    refine_payload = _run_json(
        ["campaign", "refine", campaign_path.as_posix(), "--write", "--create-beads", "--json"],
        capsys,
    )
    campaign = _read_json(campaign_path)
    goal_paths = [Path(path) for path in campaign["artifacts"]["goals"]]
    evidence_paths = [Path(path) for path in campaign["artifacts"]["evidence_plans"]]
    spec_paths = [Path(path) for path in campaign["artifacts"]["specs"]]
    adr_paths = [Path(path) for path in campaign["artifacts"]["adrs"]]

    assert refine_payload["beads"]["requested"] is True
    assert refine_payload["beads"]["ok"] is True
    assert refine_payload["beads"]["epic_id"] == "dpcx-pilot-001"
    assert len(refine_payload["beads"]["issue_ids"]) == len(goal_paths)
    assert len(beads_calls) == len(goal_paths) + 1
    assert all(path.exists() for path in spec_paths)
    assert adr_paths and all(path.exists() for path in adr_paths)

    assert _run_json(["campaign", "lint", campaign_path.as_posix(), "--json"], capsys)["valid"]
    loop_status = _run_json(["loop", "status", loop_path.as_posix(), "--json"], capsys)
    assert loop_status["ok"] is True
    assert loop_status["ready_node_ids"]

    handoff = _run_json(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
            "--driver",
            "codex",
            "--supervised",
            "--json",
        ],
        capsys,
    )
    next_goal = handoff["next"]
    assert next_goal["goal_id"] == _read_json(goal_paths[0])["id"]
    assert next_goal["commands"]["evidence_run"].startswith(
        f"dp evidence run {evidence_paths[0].as_posix()} --output docs/evidence-runs/"
    )
    assert next_goal["commands"]["verify_fresh"].startswith(
        f"dp verify --goal {goal_paths[0].as_posix()} --evidence-output docs/evidence-runs/"
    )

    active_recovery = _run_json(["campaign", "recover", campaign_path.as_posix(), "--json"], capsys)
    assert active_recovery["resume"]["action"] == "resume_claimed_goal"

    verify_payload = _run_json(["verify", "--goal", goal_paths[0].as_posix(), "--json"], capsys)
    assert verify_payload["ok"] is True
    evidence_artifact = Path(verify_payload["evidence"]["path"])
    assert evidence_artifact.exists()
    assert _last_goal_event()["event"] == "verified"

    post_verify_recovery = _run_json(
        ["campaign", "recover", campaign_path.as_posix(), "--json"], capsys
    )
    assert post_verify_recovery["resume"]["action"] == "claim_next_goal"

    decision_goal = _first_goal_with_route(goal_paths, "needs_decision")
    block_payload = _run_json(
        [
            "goal",
            "block",
            decision_goal.as_posix(),
            "--reason",
            "needs_decision",
            "--write-artifact",
            "--json",
        ],
        capsys,
    )
    assert block_payload["ok"] is True
    assert block_payload["routing"]["artifact"]["kind"] == "adr"
    assert Path(block_payload["routing"]["artifact"]["path"]).exists()
    assert block_payload["routing"]["beads"]["issue_id"].startswith("dpcx-pilot-")

    blocked_recovery = _run_json(
        ["campaign", "recover", campaign_path.as_posix(), "--json"], capsys
    )
    assert blocked_recovery["resume"]["action"] == "resolve_blocker"

    summary = {
        "scenario": "field_report_cli",
        "campaign_id": init_payload["campaign_id"],
        "goals": len(goal_paths),
        "evidence_plans": len(evidence_paths),
        "child_specs": len(spec_paths),
        "adrs": len(adr_paths),
        "beads": {
            "requested": refine_payload["beads"]["requested"],
            "created_issue_count": len(refine_payload["beads"]["issue_ids"]),
            "operation_count": len(refine_payload["beads"]["operations"]),
        },
        "first_handoff_emitted": handoff["ok"],
        "active_recovery_action": active_recovery["resume"]["action"],
        "evidence_artifact": evidence_artifact.as_posix(),
        "verified_event": True,
        "post_verify_recovery_action": post_verify_recovery["resume"]["action"],
        "blocker_artifact": block_payload["routing"]["artifact"]["path"],
        "blocked_recovery_action": blocked_recovery["resume"]["action"],
    }
    summary_paths = _write_pilot_summary(summary)

    assert summary_paths["json"].exists()
    assert summary_paths["markdown"].exists()
    assert _read_json(summary_paths["json"]) == summary
    assert "SPEC-80.19 Field Report CLI Pilot" in summary_paths["markdown"].read_text(
        encoding="utf-8"
    )


def _install_fake_beads(monkeypatch) -> list[list[str]]:
    campaign_refine = importlib.import_module("dp.core.campaign_refine")
    blocker_routing = importlib.import_module("dp.core.blocker_routing")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        issue_id = f"dpcx-pilot-{len(calls):03d}"
        return CommandResult(returncode=0, stdout=json.dumps({"id": issue_id}) + "\n", stderr="")

    monkeypatch.setattr(campaign_refine, "run_bd", fake_run_bd)
    monkeypatch.setattr(blocker_routing, "run_bd", fake_run_bd)
    return calls


def _copy_fixture(tmp_path: Path, source: Path, relative_target: str) -> Path:
    target = tmp_path / relative_target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return Path(relative_target)


def _run_json(args: list[str], capsys) -> dict:
    exit_code = main(args)
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0, payload
    return payload


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _last_goal_event() -> dict:
    events = [
        json.loads(line)
        for line in Path(".dp/goals/events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return events[-1]


def _first_goal_with_route(goal_paths: list[Path], route: str) -> Path:
    for path in goal_paths:
        goal = _read_json(path)
        routes = goal.get("blocked_routes", {})
        if isinstance(routes, dict) and route in routes:
            return path
    raise AssertionError(f"No generated goal declared blocked route {route}.")


def _write_pilot_summary(summary: dict) -> dict[str, Path]:
    output_dir = Path("docs/pilots")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "SPEC-80.19-field-report-cli-summary.json"
    markdown_path = output_dir / "SPEC-80.19-field-report-cli-summary.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown_summary(summary), encoding="utf-8")
    return {
        "json": json_path,
        "markdown": markdown_path,
    }


def _render_markdown_summary(summary: dict) -> str:
    return (
        "# SPEC-80.19 Field Report CLI Pilot\n\n"
        f"- Campaign: `{summary['campaign_id']}`\n"
        f"- Goals: {summary['goals']}\n"
        f"- Evidence plans: {summary['evidence_plans']}\n"
        f"- Child specs: {summary['child_specs']}\n"
        f"- ADRs: {summary['adrs']}\n"
        f"- Beads issues created: {summary['beads']['created_issue_count']}\n"
        f"- First handoff emitted: {str(summary['first_handoff_emitted']).lower()}\n"
        f"- Evidence artifact: `{summary['evidence_artifact']}`\n"
        f"- Recovery after verification: `{summary['post_verify_recovery_action']}`\n"
        f"- Recovery after blocker: `{summary['blocked_recovery_action']}`\n"
    )
