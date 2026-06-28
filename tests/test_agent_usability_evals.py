from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

FIXTURES = Path("tests/fixtures/spec81_projects")


def test_agent_eval_reports_required_categories(capsys) -> None:
    exit_code = main(["agent", "eval", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    categories = {item["category"] for item in payload["results"]}
    assert {
        "bootstrap-first-command",
        "next-action-quality",
        "error-repair-routing",
        "instruction-preservation",
        "legacy-project-adoption",
        "skill-triggering",
        "hook-audit-correctness",
        "token-budget-compliance",
        "resume-after-compaction",
        "no-ready-loop-handling",
    } <= categories
    assert payload["golden_transcript"][0] == "dp agent bootstrap --json --detail brief"


def test_agent_eval_reports_fixture_backed_transcripts(capsys) -> None:
    exit_code = main(["agent", "eval", "--json"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    transcripts = {item["id"]: item for item in payload["transcripts"]}

    assert payload["schema_version"] == "dp.agent_eval.v1"
    assert payload["metrics"]["fixture_backed_categories"] >= 7
    assert payload["metrics"]["transcript_step_count"] >= 7
    assert len(output) <= 8_000

    bootstrap = transcripts["bootstrap-first-command"]
    assert bootstrap["fixture"] == "repo_with_root_agents"
    assert bootstrap["steps"][0]["command"] == "dp agent bootstrap --json --detail brief"
    assert bootstrap["steps"][0]["exit_code"] == 0

    instructions = transcripts["instruction-preservation"]
    assert instructions["fixture"] == "repo_with_nested_agents"
    assert instructions["steps"][0]["observed"]["nested_agents"] >= 1

    adoption = transcripts["legacy-project-adoption"]
    assert adoption["fixture"] == "old_dp_project_minimal"
    assert adoption["steps"][0]["observed"]["classification"] == "legacy_dp"

    hook_audit = transcripts["hook-audit-correctness"]
    assert hook_audit["fixture"] == "repo_with_conflicting_hooks"
    assert "hook_calls_llm" in hook_audit["steps"][0]["observed"]["finding_codes"]

    no_ready = transcripts["no-ready-loop-handling"]
    assert no_ready["fixture"] == "campaign_with_no_ready_nodes"
    assert no_ready["steps"][0]["exit_code"] == 1
    assert no_ready["steps"][0]["observed_error_code"] == "no_ready_goal"
    assert no_ready["steps"][0]["hints"][0]["code"] == "DP-HINT-LOOP-NO-READY-NODES"


def test_spec81_eval_project_fixtures_are_executable_contracts() -> None:
    assert (FIXTURES / "campaign_with_ready_goal/dp-policy.json").is_file()
    assert (FIXTURES / "campaign_with_ready_goal/loops/ready.json").is_file()
    assert (FIXTURES / "campaign_with_no_ready_nodes/dp-policy.json").is_file()
    assert (FIXTURES / "campaign_with_no_ready_nodes/loops/no_ready.json").is_file()
    assert (FIXTURES / "campaign_with_no_ready_nodes/.dp/goals/events.jsonl").is_file()
    assert (FIXTURES / "evidence_failure/dp-policy.json").is_file()
    assert (FIXTURES / "evidence_failure/docs/evidence/failure.json").is_file()
