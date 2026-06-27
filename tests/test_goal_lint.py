from __future__ import annotations

import json
from pathlib import Path

import pytest

from dp.cli.main import main

FIXTURE_DIR = Path("tests/fixtures/goals")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "valid_spec_70_01.json",
        "valid_campaign_node.json",
    ],
)
def test_goal_lint_accepts_valid_fixtures(fixture_name: str, capsys) -> None:
    exit_code = main(["goal", "lint", (FIXTURE_DIR / fixture_name).as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["errors"] == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_exit", "expected_code"),
    [
        ("invalid_vague_objective.json", 1, "vague_objective"),
        ("invalid_missing_evidence.json", 1, "missing_evidence"),
        ("invalid_missing_blocked_terminal.json", 1, "missing_blocked_terminal"),
        ("invalid_missing_success_terminal.json", 1, "missing_success_terminal"),
        ("invalid_raw_shell_command.json", 1, "raw_shell_prohibited"),
        ("invalid_unsupported_schema.json", 2, "unsupported_schema"),
        ("invalid_campaign_without_nodes.json", 1, "campaign_without_nodes"),
        ("invalid_self_report_success.json", 1, "self_report_success"),
        ("invalid_unknown_blocker_route.json", 1, "unknown_blocker_route"),
    ],
)
def test_goal_lint_rejects_invalid_fixtures(
    fixture_name: str,
    expected_exit: int,
    expected_code: str,
    capsys,
) -> None:
    exit_code = main(["goal", "lint", (FIXTURE_DIR / fixture_name).as_posix(), "--json"])

    assert exit_code == expected_exit
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert expected_code in {error["code"] for error in payload["errors"]}


def test_goal_lint_reports_missing_file_as_input_error(capsys) -> None:
    exit_code = main(["goal", "lint", "tests/fixtures/goals/missing.json", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"][0]["code"] == "missing_file"


def test_goal_lint_reports_non_object_input_as_input_error(tmp_path: Path, capsys) -> None:
    path = tmp_path / "goal.json"
    path.write_text("[]", encoding="utf-8")

    exit_code = main(["goal", "lint", path.as_posix(), "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"][0]["code"] == "json_object_required"
