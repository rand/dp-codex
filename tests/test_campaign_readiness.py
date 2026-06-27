from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

GOAL_FIXTURE_DIR = Path("tests/fixtures/goals")


def test_campaign_ready_dry_run_passes_without_writing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_ready_campaign(tmp_path, two_nodes=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "ready", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "campaign.ready"
    assert payload["ready"] is True
    assert payload["write"] is False
    assert payload["written"] is False
    assert payload["checks"][-1] == {"name": "graph_readiness", "ok": True}
    assert payload["errors"] == []

    campaign = json.loads((tmp_path / campaign_path).read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "draft"
    assert "readiness" not in campaign


def test_campaign_ready_write_promotes_draft_campaign(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_ready_campaign(tmp_path, two_nodes=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "ready", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["ready"] is True
    assert payload["write"] is True
    assert payload["written"] is True
    assert payload["state"] == {"before": "draft", "after": "ready"}
    assert payload["readiness"]["mode"] == "deterministic_campaign_ready"
    assert payload["readiness"]["network_calls"] is False
    assert payload["readiness"]["llm_judgment"] is False
    assert payload["readiness"]["provenance"]["kind"] == "deterministic_campaign_ready"

    campaign = json.loads((tmp_path / campaign_path).read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "ready"
    assert campaign["readiness"]["mode"] == "deterministic_campaign_ready"
    assert campaign["readiness"]["provenance"]["network_calls"] is False


def test_campaign_ready_rejects_unresolved_refinement_without_writing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_ready_campaign(tmp_path, two_nodes=False)
    goal_path = tmp_path / "goals/one.json"
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    goal["refinement"]["state"] = "needs_validator"
    goal_path.write_text(json.dumps(goal), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "ready", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["ready"] is False
    assert payload["written"] is False
    assert "unresolved_refinement_state" in {error["code"] for error in payload["errors"]}
    campaign = json.loads((tmp_path / campaign_path).read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "draft"


def test_campaign_ready_rejects_missing_node_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_ready_campaign(tmp_path, two_nodes=False)
    loop_path = tmp_path / "loops/main.json"
    loop = json.loads(loop_path.read_text(encoding="utf-8"))
    del loop["nodes"][0]["evidence_plan"]
    loop_path.write_text(json.dumps(loop), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "ready", campaign_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is False
    assert "missing_node_evidence" in {error["code"] for error in payload["errors"]}


def test_campaign_ready_rejects_llm_dependency_not_materialized(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_ready_campaign(tmp_path, two_nodes=True)
    goal_path = tmp_path / "goals/two.json"
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    goal["refinement"]["llm"] = {
        "dependencies": ["GOAL-SPEC-70.01"],
        "provenance": {
            "kind": "llm",
            "provider": "openai",
            "provider_source": "calling_agent",
            "model": "gpt-test",
        },
    }
    goal_path.write_text(json.dumps(goal), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "ready", campaign_path.as_posix(), "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "llm_dependency_not_materialized" in {
        error["code"] for error in payload["errors"]
    }


def _write_ready_campaign(tmp_path: Path, *, two_nodes: bool) -> Path:
    (tmp_path / "docs/primary").mkdir(parents=True)
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "goals").mkdir()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "loops").mkdir()

    (tmp_path / "docs/primary/spec.md").write_text("# Primary Spec\n", encoding="utf-8")
    (tmp_path / "docs/specs/one.md").write_text("# Node One\n", encoding="utf-8")
    (tmp_path / "docs/specs/two.md").write_text("# Node Two\n", encoding="utf-8")

    _write_goal(
        tmp_path / "goals/one.json",
        fixture="valid_spec_70_01.json",
        evidence_path="evidence/one.json",
        spec_path="docs/specs/one.md",
    )
    _write_evidence(tmp_path / "evidence/one.json", "EVIDENCE-ONE", "GOAL-SPEC-70.01")
    nodes = [
        {
            "id": "one",
            "kind": "goal",
            "goal_id": "GOAL-SPEC-70.01",
            "goal_path": "goals/one.json",
            "beads_issue_id": "dpcx-ready.1",
            "depends_on": [],
            "evidence_plan": "evidence/one.json",
        }
    ]
    goals = ["goals/one.json"]
    evidence_plans = ["evidence/one.json"]
    if two_nodes:
        _write_goal(
            tmp_path / "goals/two.json",
            fixture="valid_campaign_node.json",
            evidence_path="evidence/two.json",
            spec_path="docs/specs/two.md",
        )
        _write_evidence(
            tmp_path / "evidence/two.json",
            "EVIDENCE-TWO",
            "GOAL-SPEC-80.01-LINT",
        )
        nodes.append(
            {
                "id": "two",
                "kind": "goal",
                "goal_id": "GOAL-SPEC-80.01-LINT",
                "goal_path": "goals/two.json",
                "beads_issue_id": "dpcx-ready.2",
                "depends_on": [],
                "evidence_plan": "evidence/two.json",
            }
        )
        goals.append("goals/two.json")
        evidence_plans.append("evidence/two.json")

    (tmp_path / "loops/main.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "LOOP-READY",
                "title": "Ready loop",
                "nodes": nodes,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "campaign.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "CAMPAIGN-READY",
                "title": "Ready campaign",
                "primary_spec": {"path": "docs/primary/spec.md"},
                "artifacts": {
                    "specs": ["docs/specs/one.md", "docs/specs/two.md"],
                    "adrs": [],
                    "goals": goals,
                    "evidence_plans": evidence_plans,
                    "loops": ["loops/main.json"],
                    "beads_epics": ["dpcx-pb5"],
                    "beads_issues": ["dpcx-ready.1", "dpcx-ready.2"],
                },
                "state": {
                    "status": "draft",
                    "current_loop": "LOOP-READY",
                    "current_goal": None,
                },
            }
        ),
        encoding="utf-8",
    )
    return Path("campaign.json")


def _write_goal(
    path: Path,
    *,
    fixture: str,
    evidence_path: str,
    spec_path: str,
) -> None:
    goal = json.loads((GOAL_FIXTURE_DIR / fixture).read_text(encoding="utf-8"))
    goal["source"]["path"] = spec_path
    goal["evidence"]["evidence_plan"] = evidence_path
    goal["refinement"] = {
        "state": "implementation_candidate",
        "classification": "implementation",
        "spec_path": spec_path,
        "adr_path": None,
        "routes": [],
        "signals": {
            "requirements": ["The node has reviewed implementation requirements."],
            "evidence": ["The node has a deterministic evidence plan."],
            "decisions": [],
            "blockers": [],
            "dependencies": [],
        },
        "provenance": {
            "kind": "deterministic_refine",
            "network_calls": False,
        },
    }
    path.write_text(json.dumps(goal), encoding="utf-8")


def _write_evidence(path: Path, evidence_id: str, goal_id: str) -> None:
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
                        "argv": ["dp", "goal", "lint", "goals/one.json", "--json"],
                        "timeout_seconds": 30,
                        "success_exit_codes": [0],
                        "assertions": [{"type": "stdout_json"}],
                        "mutation_policy": "read_only",
                    }
                ],
                "refinement": {
                    "state": "implementation_candidate",
                    "classification": "implementation",
                    "goal_id": goal_id,
                    "spec_path": "docs/specs/one.md",
                    "routes": [],
                },
            }
        ),
        encoding="utf-8",
    )
