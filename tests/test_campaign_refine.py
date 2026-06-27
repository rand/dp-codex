from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Sequence

from dp.cli.main import main
from dp.providers.beads import CommandResult

SEMANTIC_PRIMARY_SPEC = Path("tests/fixtures/primary_specs/semantic_signals.md")


def test_campaign_refine_dry_run_reports_artifacts_without_writes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)

    exit_code = main(["campaign", "refine", campaign_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "campaign.refine"
    assert payload["written"] is False
    assert payload["beads"]["created"] is False
    assert payload["provenance"]["kind"] == "deterministic_refine"
    assert payload["provenance"]["network_calls"] is False
    assert payload["planned"]["specs"]
    assert payload["planned"]["adrs"]
    assert payload["planned"]["goals"][0]["evidence_path"].startswith("docs/evidence/")
    assert not Path(payload["planned"]["specs"][0]["path"]).exists()


def test_campaign_refine_write_updates_campaign_and_goal_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)

    exit_code = main(["campaign", "refine", campaign_path.as_posix(), "--write", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["written"] is True
    spec_paths = [Path(item["path"]) for item in payload["planned"]["specs"]]
    adr_paths = [Path(item["path"]) for item in payload["planned"]["adrs"]]
    assert spec_paths
    assert adr_paths
    assert all(path.exists() for path in spec_paths)
    assert all(path.exists() for path in adr_paths)

    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "draft"
    assert set(campaign["artifacts"]["specs"]) >= {path.as_posix() for path in spec_paths}
    assert set(campaign["artifacts"]["adrs"]) >= {path.as_posix() for path in adr_paths}
    assert campaign["refinement"]["provenance"]["kind"] == "deterministic_refine"

    goal_path = Path(campaign["artifacts"]["goals"][0])
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    assert goal["refinement"]["spec_path"] == spec_paths[0].as_posix()
    assert goal["refinement"]["state"] in {
        "implementation_candidate",
        "evidence_candidate",
        "needs_decision",
        "needs_specification",
        "needs_validator",
    }

    evidence_path = Path(campaign["artifacts"]["evidence_plans"][0])
    evidence_plan = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence_plan["refinement"]["goal_id"] == goal["id"]
    assert evidence_plan["refinement"]["spec_path"] == spec_paths[0].as_posix()
    assert evidence_plan["refinement"]["provenance"]["kind"] == "deterministic_refine"


def test_campaign_refine_llm_emits_calling_agent_request(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)

    exit_code = main(["campaign", "refine", campaign_path.as_posix(), "--llm", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["mode"] == "llm_request"
    assert payload["written"] is False
    assert payload["provenance"]["kind"] == "llm_request"
    assert payload["provenance"]["provider_source"] == "calling_agent"
    assert payload["provenance"]["network_calls"] is False
    assert payload["request"]["provider"] == "calling_agent"
    assert payload["request"]["response_schema"] == (
        "docs/schemas/campaign-refine-llm-response.schema.json"
    )
    assert payload["request"]["prompt_hash"].startswith("sha256:")
    assert "Return JSON only" in payload["request"]["prompt"]


def test_campaign_refine_imports_valid_llm_response(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)
    request_payload = _llm_request(campaign_path, capsys)
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    goal_path = Path(campaign["artifacts"]["goals"][0])
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    response_path = tmp_path / "llm-response.json"
    _write_llm_response(
        response_path,
        campaign_id=request_payload["campaign_id"],
        prompt_hash=request_payload["request"]["prompt_hash"],
        goal_id=goal["id"],
    )

    exit_code = main(
        [
            "campaign",
            "refine",
            campaign_path.as_posix(),
            "--llm-response",
            response_path.as_posix(),
            "--write",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["mode"] == "llm_import"
    assert payload["written"] is True
    assert payload["provenance"]["kind"] == "llm"
    assert payload["provenance"]["provider"] == "openai"
    assert payload["provenance"]["provider_source"] == "calling_agent"
    assert payload["provenance"]["model"] == "gpt-test"
    assert payload["provenance"]["network_calls"] is True
    assert payload["llm"]["imported_nodes"] == [goal["id"]]

    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "draft"
    assert campaign["refinement"]["llm"]["provenance"]["kind"] == "llm"

    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    assert goal["refinement"]["llm"]["objective"] == "Refine this node into a testable slice."
    assert goal["refinement"]["llm"]["requirements"] == ["Keep gates deterministic."]

    evidence_path = Path(campaign["artifacts"]["evidence_plans"][0])
    evidence_plan = json.loads(evidence_path.read_text(encoding="utf-8"))
    llm_evidence = evidence_plan["refinement"]["llm"]["evidence"]
    assert llm_evidence[0]["argv"] == ["dp", "goal", "lint", goal_path.as_posix(), "--json"]


def test_campaign_refine_rejects_llm_response_unknown_goal_without_writes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)
    request_payload = _llm_request(campaign_path, capsys)
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    goal_path = Path(campaign["artifacts"]["goals"][0])
    before = goal_path.read_text(encoding="utf-8")
    response_path = tmp_path / "bad-goal-response.json"
    _write_llm_response(
        response_path,
        campaign_id=request_payload["campaign_id"],
        prompt_hash=request_payload["request"]["prompt_hash"],
        goal_id="GOAL-does-not-exist",
    )

    exit_code = main(
        [
            "campaign",
            "refine",
            campaign_path.as_posix(),
            "--llm-response",
            response_path.as_posix(),
            "--write",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "unknown_goal_id"
    assert goal_path.read_text(encoding="utf-8") == before


def test_campaign_refine_rejects_llm_response_raw_shell_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)
    request_payload = _llm_request(campaign_path, capsys)
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    goal_path = Path(campaign["artifacts"]["goals"][0])
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    response_path = tmp_path / "raw-shell-response.json"
    _write_llm_response(
        response_path,
        campaign_id=request_payload["campaign_id"],
        prompt_hash=request_payload["request"]["prompt_hash"],
        goal_id=goal["id"],
        evidence_argv=["sh", "-c", "make check && rm -rf /"],
    )

    exit_code = main(
        [
            "campaign",
            "refine",
            campaign_path.as_posix(),
            "--llm-response",
            response_path.as_posix(),
            "--write",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "raw_shell_evidence"


def test_campaign_refine_create_beads_records_created_ids(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)
    campaign_refine = importlib.import_module("dp.core.campaign_refine")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        issue_id = f"dpcx-generated-{len(calls)}"
        return CommandResult(returncode=0, stdout=json.dumps({"id": issue_id}) + "\n", stderr="")

    monkeypatch.setattr(campaign_refine, "run_bd", fake_run_bd)

    exit_code = main(
        [
            "campaign",
            "refine",
            campaign_path.as_posix(),
            "--write",
            "--create-beads",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["beads"]["created"] is True
    assert payload["beads"]["epic_id"] == "dpcx-generated-1"
    assert payload["beads"]["issue_ids"]
    assert calls[0][0] == "create"
    assert "--type" in calls[0]
    assert "epic" in calls[0]
    assert any("--parent" in call for call in calls[1:])

    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert campaign["artifacts"]["beads_epics"] == ["dpcx-generated-1"]
    assert set(campaign["artifacts"]["beads_issues"]) == set(payload["beads"]["issue_ids"])


def test_campaign_refine_create_beads_requires_write(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)

    exit_code = main(["campaign", "refine", campaign_path.as_posix(), "--create-beads", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "create_beads_requires_write"


def _write_campaign(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> Path:
    primary_spec = tmp_path / "docs/primary/semantic-signals.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(SEMANTIC_PRIMARY_SPEC.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "campaign",
                "init",
                "--primary-spec",
                "docs/primary/semantic-signals.md",
                "--write",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    return Path(payload["artifacts"]["campaign"])


def _llm_request(campaign_path: Path, capsys) -> dict[str, object]:
    assert main(["campaign", "refine", campaign_path.as_posix(), "--llm", "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def _write_llm_response(
    path: Path,
    *,
    campaign_id: str,
    prompt_hash: str,
    goal_id: str,
    evidence_argv: list[str] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "campaign_id": campaign_id,
                "prompt_hash": prompt_hash,
                "provider": "openai",
                "provider_source": "calling_agent",
                "model": "gpt-test",
                "created_at": "2026-06-27T00:00:00Z",
                "campaign_rationale": "Use semantic refinement to make the draft node sharper.",
                "nodes": [
                    {
                        "goal_id": goal_id,
                        "objective": "Refine this node into a testable slice.",
                        "rationale": "The primary spec section contains implementation cues.",
                        "non_goals": ["Do not mark the campaign verified."],
                        "requirements": ["Keep gates deterministic."],
                        "evidence": [
                            {
                                "kind": "registered_command",
                                "argv": evidence_argv
                                or [
                                    "dp",
                                    "goal",
                                    "lint",
                                    f"docs/goals/{goal_id}.json",
                                    "--json",
                                ],
                                "rationale": "Goal contract lint is the first deterministic gate.",
                            }
                        ],
                        "decisions": ["No architecture decision required for this node."],
                        "dependencies": [],
                        "read_first": ["docs/primary/semantic-signals.md"],
                        "allowed_paths": ["docs"],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
