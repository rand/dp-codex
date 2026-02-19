from __future__ import annotations

import importlib
import json

import pytest

from dp.core.review import ReviewFinding, ReviewReport

cli_main = importlib.import_module("dp.cli.main")


def test_review_command_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = ReviewReport(
        findings=(
            ReviewFinding(
                check_id="worktree-dirty",
                severity="blocking",
                message="Working tree has uncommitted changes.",
                path="dp/core/example.py",
            ),
        ),
        blocking_count=1,
        advisory_count=0,
        ready_to_commit=False,
    )
    monkeypatch.setattr(cli_main, "run_review", lambda _: report)

    exit_code = cli_main.main(["review", "--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready_to_commit"] is False
    assert payload["blocking_count"] == 1
    assert payload["findings"][0]["check_id"] == "worktree-dirty"


def test_review_command_text_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = ReviewReport(
        findings=(),
        blocking_count=0,
        advisory_count=0,
        ready_to_commit=True,
    )
    monkeypatch.setattr(cli_main, "run_review", lambda _: report)

    exit_code = cli_main.main(["review"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Commit readiness: READY" in output
    assert "No findings." in output
