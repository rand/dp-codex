from __future__ import annotations

import json

from dp.cli.main import main


def test_goal_status_detail_brief_uses_agent_envelope(capsys) -> None:
    exit_code = main(
        [
            "goal",
            "status",
            "tests/fixtures/goals/valid_spec_70_01.json",
            "--json",
            "--detail",
            "brief",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "dp.response.v1"
    assert payload["affordances"]["phase"] == "work"
    assert payload["next_actions"]
    assert payload["expansions"][0]["command"].endswith("--detail full")


def test_campaign_status_detail_brief_omits_large_loop_payload(capsys) -> None:
    exit_code = main(
        [
            "campaign",
            "status",
            "tests/fixtures/campaigns/valid_spec_80_06.json",
            "--json",
            "--detail",
            "brief",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "dp.response.v1"
    assert payload["result"]["campaign_id"] == "CAMPAIGN-SPEC-80.06"
    assert "loop" not in payload["result"]


def test_evidence_failure_routes_to_repair_hint(capsys) -> None:
    exit_code = main(
        [
            "evidence",
            "run",
            "tests/fixtures/evidence/invalid_run_assertion_failure.json",
            "--json",
            "--detail",
            "normal",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    codes = {hint["code"] for hint in payload["hints"]}
    assert "DP-HINT-EVIDENCE-FAILED" in codes
    assert payload["result"]["failed_checks"][0]["id"] == "goal-lint-wrong-assertion"


def test_doctor_detail_brief_has_next_action(capsys) -> None:
    exit_code = main(["doctor", "--json", "--detail", "brief"])

    assert exit_code in {0, 2}
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "dp.response.v1"
    assert payload["next_actions"][0]["command"] == "dp agent bootstrap --json --detail brief"
