from __future__ import annotations

import importlib
import json

import pytest

from dp.enforcement.engine import EnforcementCheckResult, EnforcementReport

cli_main = importlib.import_module("dp.cli.main")


def test_enforce_cli_json_output_and_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = EnforcementReport(
        stage="pre-commit",
        mode="strict",
        policy_path="dp-policy.json",
        bypassed=False,
        bypass_reason=None,
        blocked=True,
        checks=(
            EnforcementCheckResult(
                check="tests",
                status="failed",
                blocking=True,
                command="make test",
                exit_code=2,
                duration_seconds=1.2,
                message="Check failed.",
            ),
        ),
    )

    def fake_run_enforcement(*, stage: str, policy_path, repo_root):
        assert stage == "pre-commit"
        assert policy_path.name == "dp-policy.json"
        assert repo_root.exists()
        return report

    monkeypatch.setattr(cli_main, "run_enforcement", fake_run_enforcement)

    exit_code = cli_main.main(["enforce", "pre-commit", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["blocked"] is True
    assert payload["checks"][0]["check"] == "tests"


def test_enforce_cli_text_output_for_bypass(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = EnforcementReport(
        stage="pre-push",
        mode="guided",
        policy_path="dp-policy.json",
        bypassed=True,
        bypass_reason="urgent rollback",
        blocked=False,
        checks=(),
    )
    monkeypatch.setattr(cli_main, "run_enforcement", lambda **_: report)

    exit_code = cli_main.main(["enforce", "pre-push"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Enforcement stage: pre-push" in output
    assert "Bypass: active" in output
    assert "urgent rollback" in output


def test_enforce_cli_invalid_policy_path_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli_main.main(
        [
            "enforce",
            "pre-commit",
            "--policy",
            "missing-policy.json",
            "--json",
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "Policy file not found" in payload["error"]
