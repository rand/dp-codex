from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main
from dp.core import agent_experience
from dp.core.campaign_manifest import CampaignCommandResult


def test_agent_bootstrap_brief_is_enveloped_and_compact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    (tmp_path / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
    (tmp_path / "dp-policy.json").write_text('{"mode": "guided"}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["agent", "bootstrap", "--json", "--detail", "brief"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert len(output) <= 2_000
    assert payload["schema_version"] == "dp.response.v1"
    assert payload["affordances"]["phase"] == "orient"
    assert payload["result"]["repo"]["policy_path"] == "dp-policy.json"


def test_agent_capabilities_cli_is_compact(capsys) -> None:
    exit_code = main(["agent", "capabilities", "--json"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert len(output) <= 5_000
    assert payload["schema_version"] == "dp.capabilities.v1"


def test_campaign_routing_uses_derived_state_and_ignores_sidecars(
    tmp_path: Path,
    monkeypatch,
) -> None:
    campaign_dir = tmp_path / "docs/campaigns"
    campaign_dir.mkdir(parents=True)
    for name in (
        "CAMPAIGN-a-verified.json",
        "CAMPAIGN-b-active.json",
        "CAMPAIGN-b-active.needs_refinement.json",
        "CAMPAIGN-c-blocked.json",
    ):
        (campaign_dir / name).write_text("{}\n", encoding="utf-8")

    statuses = {
        "CAMPAIGN-a-verified.json": "verified",
        "CAMPAIGN-b-active.json": "active",
        "CAMPAIGN-c-blocked.json": "blocked",
    }

    def fake_status(path: Path) -> CampaignCommandResult:
        status = statuses.get(path.name)
        if status is None:
            return CampaignCommandResult(
                payload={"error": {"code": "missing_id"}},
                exit_code=2,
            )
        return CampaignCommandResult(
            payload={
                "campaign_id": path.stem,
                "derived_status": status,
            },
            exit_code=0,
        )

    monkeypatch.setattr(agent_experience, "campaign_status", fake_status)

    campaigns = agent_experience._campaigns(tmp_path, detail="full")

    assert campaigns["active"] == ["docs/campaigns/CAMPAIGN-b-active.json"]
    assert campaigns["blocked"] == ["docs/campaigns/CAMPAIGN-c-blocked.json"]
    assert campaigns["historical"] == ["docs/campaigns/CAMPAIGN-a-verified.json"]
    assert campaigns["invalid"] == [
        "docs/campaigns/CAMPAIGN-b-active.needs_refinement.json",
    ]
    actions = agent_experience._bootstrap_next_actions("current_spec81", campaigns, None)
    assert actions[0]["command"].startswith(
        "dp campaign status docs/campaigns/CAMPAIGN-b-active.json",
    )
    artifacts = agent_experience._bootstrap_artifacts(tmp_path, campaigns)
    assert [item["path"] for item in artifacts] == [
        "docs/campaigns/CAMPAIGN-b-active.json",
        "docs/campaigns/CAMPAIGN-c-blocked.json",
    ]


def test_campaign_routing_does_not_recover_verified_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    campaign = tmp_path / "docs/campaigns/CAMPAIGN-finished.json"
    campaign.parent.mkdir(parents=True)
    campaign.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        agent_experience,
        "campaign_status",
        lambda _path: CampaignCommandResult(
            payload={
                "campaign_id": "CAMPAIGN-finished",
                "derived_status": "verified",
            },
            exit_code=0,
        ),
    )

    campaigns = agent_experience._campaigns(tmp_path, detail="full")
    actions = agent_experience._bootstrap_next_actions("current_spec81", campaigns, None)

    assert campaigns["active"] == []
    assert campaigns["blocked"] == []
    assert all(action["id"] != "recover_campaign" for action in actions)
