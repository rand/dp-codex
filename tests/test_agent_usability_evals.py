from __future__ import annotations

import json

from dp.cli.main import main


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
