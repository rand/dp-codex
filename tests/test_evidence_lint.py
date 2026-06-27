from __future__ import annotations

import json
from pathlib import Path

import pytest

from dp.cli.main import main

FIXTURE_DIR = Path("tests/fixtures/evidence")


def test_evidence_lint_accepts_valid_fixture(capsys) -> None:
    exit_code = main(
        ["evidence", "lint", (FIXTURE_DIR / "valid_spec_80_05.json").as_posix(), "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["evidence_id"] == "EVIDENCE-SPEC-80.05"
    assert payload["goal_id"] == "GOAL-SPEC-80.05"
    assert payload["errors"] == []


@pytest.mark.parametrize(
    ("fixture_name", "expected_exit", "expected_code"),
    [
        ("invalid_missing_timeout.json", 1, "missing_timeout"),
        ("invalid_raw_shell_string.json", 1, "raw_shell_prohibited"),
        ("invalid_argv_string.json", 1, "invalid_argv"),
        ("invalid_unregistered_command.json", 1, "unregistered_command"),
        ("invalid_missing_assertions.json", 1, "missing_assertions"),
        ("invalid_mutating_without_policy.json", 1, "invalid_mutation_policy"),
        ("invalid_unsupported_schema.json", 2, "unsupported_schema"),
        ("invalid_bad_success_exit_codes.json", 1, "invalid_success_exit_code"),
    ],
)
def test_evidence_lint_rejects_invalid_fixtures(
    fixture_name: str,
    expected_exit: int,
    expected_code: str,
    capsys,
) -> None:
    exit_code = main(["evidence", "lint", (FIXTURE_DIR / fixture_name).as_posix(), "--json"])

    assert exit_code == expected_exit
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert expected_code in {error["code"] for error in payload["errors"]}


def test_evidence_lint_reports_missing_file_as_input_error(capsys) -> None:
    exit_code = main(["evidence", "lint", "tests/fixtures/evidence/missing.json", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"][0]["code"] == "missing_file"


def test_evidence_lint_reports_non_object_input_as_input_error(
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "evidence.json"
    path.write_text("[]", encoding="utf-8")

    exit_code = main(["evidence", "lint", path.as_posix(), "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"][0]["code"] == "json_object_required"


def test_evidence_lint_allows_shell_characters_in_non_executable_assertion_text(
    tmp_path: Path,
    capsys,
) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "EVIDENCE-TEXT-ASSERTION",
                "goal_id": "GOAL-SPEC-80.05",
                "checks": [
                    {
                        "id": "stdout-text",
                        "kind": "registered_command",
                        "argv": ["dp", "doctor", "--json"],
                        "timeout_seconds": 30,
                        "success_exit_codes": [0],
                        "assertions": [
                            {
                                "type": "stdout_contains",
                                "text": "pipes | and semicolons ; are output text",
                            }
                        ],
                        "mutation_policy": "read_only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["evidence", "lint", path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
