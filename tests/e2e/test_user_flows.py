from __future__ import annotations

import json
import shutil
from pathlib import Path

from dp.cli.main import main

REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_FIXTURES = REPO_ROOT / "tests/fixtures/goals"
SPEC81_FIXTURES = REPO_ROOT / "tests/fixtures/spec81_projects"


def test_e2e_human_campaign_handoff_verify_and_recover(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    status = _run_json(["campaign", "status", campaign_path.as_posix(), "--json"], capsys)
    assert status["resume"]["action"] == "claim_next_goal"

    handoff = _run_json(
        [
            "campaign",
            "run",
            campaign_path.as_posix(),
            "--driver",
            "codex",
            "--supervised",
            "--managed",
            "--json",
        ],
        capsys,
    )
    assert handoff["stop_reason"] == "handoff_claimed"
    assert handoff["next"]["goal_id"] == "GOAL-SPEC-70.01"
    assert handoff["next"]["commands"]["verify_fresh"].startswith(
        "dp verify --goal goals/one.json --evidence-output docs/evidence-runs/"
    )
    assert handoff["launched"] is False
    assert handoff["autonomous"] is False

    active = _run_json(["campaign", "recover", campaign_path.as_posix(), "--json"], capsys)
    assert active["resume"]["action"] == "resume_claimed_goal"

    verified = _run_json(["verify", "--goal", "goals/one.json", "--json"], capsys)
    assert verified["ok"] is True
    assert Path(verified["evidence"]["path"]).is_file()
    assert _goal_events()[-1]["event"] == "verified"

    recovered = _run_json(["campaign", "recover", campaign_path.as_posix(), "--json"], capsys)
    assert recovered["resume"]["action"] == "claim_next_goal"


def test_e2e_agent_bootstrap_capability_and_repair_flow(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    bootstrap = _run_json(["agent", "bootstrap", "--json", "--detail", "brief"], capsys)
    assert bootstrap["schema_version"] == "dp.response.v1"
    assert bootstrap["next_actions"]

    capabilities = _run_json(["agent", "capabilities", "--json"], capsys)
    assert capabilities["schema_version"] == "dp.capabilities.v1"
    assert any(card["name"] == "dp evidence run" for card in capabilities["toolcards"])

    agent_eval = _run_json(["agent", "eval", "--json"], capsys)
    assert agent_eval["ok"] is True
    assert agent_eval["metrics"]["fixture_backed_categories"] >= 7

    fixture = tmp_path / "evidence_failure"
    shutil.copytree(SPEC81_FIXTURES / "evidence_failure", fixture)
    monkeypatch.chdir(fixture)

    failed = _run_json(
        ["evidence", "run", "docs/evidence/failure.json", "--json", "--detail", "normal"],
        capsys,
        expected_exit=1,
    )
    assert failed["schema_version"] == "dp.response.v1"
    assert failed["hints"][0]["code"] == "DP-HINT-EVIDENCE-FAILED"
    assert failed["next_actions"][0]["command"] == "dp explain DP-HINT-EVIDENCE-FAILED --json"

    explained = _run_json(["explain", "DP-HINT-EVIDENCE-FAILED", "--json"], capsys)
    assert explained["code"] == "DP-HINT-EVIDENCE-FAILED"
    assert explained["next_actions"]


def test_e2e_adoption_preserves_instructions_and_requires_reviewable_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    shutil.copytree(SPEC81_FIXTURES / "old_dp_project_with_agents_md", tmp_path, dirs_exist_ok=True)
    original_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    inspected = _run_json(["adopt", "inspect", "--json"], capsys)
    assert inspected["classification"] == "legacy_dp"

    audited = _run_json(["instructions", "audit", "--json"], capsys)
    assert audited["schema_version"] == "dp.instructions.audit.v1"

    planned = _run_json(["adopt", "plan", "--write", "--json"], capsys)
    plan_path = Path(planned["artifacts"][0]["path"])
    assert plan_path.is_file()
    assert planned["plan"]["rules"]["overwrite_agents_md"] is False

    dry_run = _run_json(["adopt", "apply", plan_path.as_posix(), "--json"], capsys)
    assert dry_run["dry_run"] is True
    assert not (tmp_path / ".dp/goals").exists()

    applied = _run_json(["adopt", "apply", plan_path.as_posix(), "--apply", "--json"], capsys)
    assert applied["dry_run"] is False
    assert (tmp_path / ".dp/goals").is_dir()
    assert (tmp_path / ".dp/campaigns").is_dir()
    assert (tmp_path / ".agents/skills/dp-agent-bootstrap/SKILL.md").is_file()

    verified = _run_json(["adopt", "verify", "--json"], capsys)
    assert verified["ok"] is True
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == original_agents
    assert not (tmp_path / "AGENTS.override.md").exists()


def _write_campaign_project(root: Path) -> Path:
    for directory in (
        "docs/primary",
        "docs/specs",
        "docs/adr",
        "docs/evidence",
        "goals",
        "loops",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)

    (root / "docs/primary/spec.md").write_text("# Primary Spec\n", encoding="utf-8")
    (root / "docs/specs/SPEC-80-e2e.md").write_text("# SPEC-80 E2E\n", encoding="utf-8")
    (root / "docs/adr/ADR-e2e.md").write_text("# ADR E2E\n", encoding="utf-8")
    _write_goal(root / "goals/one.json", GOAL_FIXTURES / "valid_spec_70_01.json", "one.json")
    _write_goal(root / "goals/two.json", GOAL_FIXTURES / "valid_campaign_node.json", "two.json")
    _write_evidence(root / "docs/evidence/one.json", "EVIDENCE-E2E-ONE", "GOAL-SPEC-70.01", "one")
    _write_evidence(
        root / "docs/evidence/two.json",
        "EVIDENCE-E2E-TWO",
        "GOAL-SPEC-80.01-LINT",
        "two",
    )
    (root / "loops/main.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "LOOP-E2E",
                "title": "E2E loop",
                "nodes": [
                    {
                        "id": "first",
                        "kind": "goal",
                        "goal_id": "GOAL-SPEC-70.01",
                        "goal_path": "goals/one.json",
                        "depends_on": [],
                        "evidence_plan": "docs/evidence/one.json",
                    },
                    {
                        "id": "second",
                        "kind": "goal",
                        "goal_id": "GOAL-SPEC-80.01-LINT",
                        "goal_path": "goals/two.json",
                        "depends_on": ["first"],
                        "evidence_plan": "docs/evidence/two.json",
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    campaign_path = root / "campaign.json"
    campaign_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "CAMPAIGN-E2E",
                "title": "E2E campaign",
                "primary_spec": {"path": "docs/primary/spec.md"},
                "artifacts": {
                    "specs": ["docs/specs/SPEC-80-e2e.md"],
                    "adrs": ["docs/adr/ADR-e2e.md"],
                    "goals": ["goals/one.json", "goals/two.json"],
                    "evidence_plans": ["docs/evidence/one.json", "docs/evidence/two.json"],
                    "loops": ["loops/main.json"],
                    "beads_epics": ["dpcx-e2e"],
                    "beads_issues": ["dpcx-e2e.1", "dpcx-e2e.2"],
                },
                "state": {
                    "status": "active",
                    "current_loop": "LOOP-E2E",
                    "current_goal": None,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return campaign_path.relative_to(root)


def _write_goal(target: Path, source: Path, evidence_name: str) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    evidence_stem = evidence_name.replace(".json", "")
    payload["evidence"]["evidence_plan"] = f"docs/evidence/{evidence_stem}.json"
    payload["evidence"]["verification_commands"] = [
        f"dp evidence run docs/evidence/{evidence_stem}.json --json",
        f"dp verify --goal goals/{evidence_name} --json",
    ]
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_evidence(path: Path, evidence_id: str, goal_id: str, goal_name: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": evidence_id,
                "goal_id": goal_id,
                "checks": [
                    {
                        "id": "goal-lint",
                        "kind": "registered_command",
                        "argv": ["dp", "goal", "lint", f"goals/{goal_name}.json", "--json"],
                        "timeout_seconds": 30,
                        "success_exit_codes": [0],
                        "assertions": [
                            {"type": "stdout_json"},
                            {"type": "json_path_equals", "path": "$.valid", "value": True},
                        ],
                        "mutation_policy": "read_only",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _run_json(
    args: list[str],
    capsys,
    *,
    expected_exit: int = 0,
) -> dict:
    exit_code = main(args)
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == expected_exit, payload
    return payload


def _goal_events() -> list[dict]:
    return [
        json.loads(line)
        for line in Path(".dp/goals/events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
