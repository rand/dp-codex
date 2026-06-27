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


def test_campaign_refine_rejects_llm_until_authoring_provider_exists(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    campaign_path = _write_campaign(tmp_path, monkeypatch, capsys)

    exit_code = main(["campaign", "refine", campaign_path.as_posix(), "--llm", "--write", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "llm_refine_not_implemented"
    assert payload["provenance"]["kind"] == "llm"
    assert payload["provenance"]["provider_source"] == "calling_agent"
    assert payload["provenance"]["network_calls"] is True


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
