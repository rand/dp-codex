from __future__ import annotations

import json
import shutil
from pathlib import Path

from dp.cli.main import main


def test_agent_bootstrap_and_capabilities_budgets(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["agent", "bootstrap", "--json", "--detail", "brief"]) == 0
    assert len(capsys.readouterr().out) <= 2_000

    assert main(["agent", "capabilities", "--json"]) == 0
    assert len(capsys.readouterr().out) <= 5_000


def test_goal_and_campaign_brief_budgets(capsys) -> None:
    assert (
        main(
            [
                "goal",
                "status",
                "tests/fixtures/goals/valid_spec_70_01.json",
                "--json",
                "--detail",
                "brief",
            ]
        )
        == 0
    )
    assert len(capsys.readouterr().out) <= 1_500

    assert (
        main(
            [
                "campaign",
                "status",
                "tests/fixtures/campaigns/valid_spec_80_06.json",
                "--json",
                "--detail",
                "brief",
            ]
        )
        == 0
    )
    assert len(capsys.readouterr().out) <= 2_500


def test_loop_next_claim_normal_budget(tmp_path: Path, monkeypatch, capsys) -> None:
    _copy_fixture_tree(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "loop",
            "next",
            "tests/fixtures/loops/valid_spec_80_04.json",
            "--claim",
            "--emit",
            "codex",
            "--json",
            "--detail",
            "normal",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["schema_version"] == "dp.response.v1"
    assert len(output) <= 7_000


def test_common_evidence_failure_budget(capsys) -> None:
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
    assert len(capsys.readouterr().out) <= 4_000


def _copy_fixture_tree(tmp_path: Path) -> None:
    source = Path("tests/fixtures")
    target = tmp_path / "tests/fixtures"
    shutil.copytree(source / "goals", target / "goals", dirs_exist_ok=True)
    shutil.copytree(source / "loops", target / "loops", dirs_exist_ok=True)
    shutil.copytree(source / "evidence", target / "evidence", dirs_exist_ok=True)
