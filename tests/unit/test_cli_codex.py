from __future__ import annotations

import importlib
import json
from typing import Sequence

import pytest

import dp.core.codex_preflight as codex_preflight
from dp.providers.beads import BeadsHealth, CommandResult

cli_main = importlib.import_module("dp.cli.main")


def test_codex_preflight_guided_reports_active_issue_and_evidence_signal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "id": "dpcx-ea9.2",
                        "title": "Add Codex integration",
                        "spec_id": "SPEC-70.03",
                        "status": "in_progress",
                        "issue_type": "task",
                        "labels": ["codex", "hooks"],
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(codex_preflight, "check_beads_health", _healthy_beads)
    monkeypatch.setattr(codex_preflight, "run_bd", fake_run_bd)
    monkeypatch.setattr(
        codex_preflight,
        "_git_changed_files",
        lambda: (["dp/cli/main.py", "tests/unit/test_cli_codex.py"], None),
    )

    exit_code = cli_main.main(["codex", "preflight", "--event", "stop", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "codex.preflight"
    assert payload["event"] == "stop"
    assert payload["mode"] == "guided"
    assert payload["ok"] is True
    assert payload["active_issue"]["id"] == "dpcx-ea9.2"
    assert payload["changed_files"] == ["dp/cli/main.py", "tests/unit/test_cli_codex.py"]
    assert payload["evidence"]["has_code_changes"] is True
    assert payload["evidence"]["has_test_changes"] is True
    assert payload["evidence"]["missing_evidence_signal"] is False
    assert calls == [
        [
            "--readonly",
            "--sandbox",
            "list",
            "--status",
            "in_progress",
            "--json",
            "-n",
            "0",
        ]
    ]


def test_codex_preflight_guided_keeps_missing_context_advisory(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(codex_preflight, "check_beads_health", _healthy_beads)
    monkeypatch.setattr(
        codex_preflight,
        "run_bd",
        lambda _: CommandResult(returncode=0, stdout="[]", stderr=""),
    )
    monkeypatch.setattr(
        codex_preflight,
        "_git_changed_files",
        lambda: (["dp/core/new_feature.py"], None),
    )

    exit_code = cli_main.main(["codex", "preflight", "--event", "stop", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["blocking_count"] == 0
    assert payload["advisory_count"] == 3
    assert payload["active_issue"] is None
    assert payload["evidence"]["missing_evidence_signal"] is True


def test_codex_preflight_strict_blocks_missing_context_and_evidence_signal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(codex_preflight, "check_beads_health", _healthy_beads)
    monkeypatch.setattr(
        codex_preflight,
        "run_bd",
        lambda _: CommandResult(returncode=0, stdout="[]", stderr=""),
    )
    monkeypatch.setattr(
        codex_preflight,
        "_git_changed_files",
        lambda: (["scripts/tool.py"], None),
    )

    exit_code = cli_main.main(
        ["codex", "preflight", "--event", "stop", "--strict", "--json"]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["blocking_count"] == 2
    assert payload["advisory_count"] == 1
    check_map = {check["id"]: check for check in payload["checks"]}
    assert check_map["active_issue"]["severity"] == "blocking"
    assert check_map["evidence_signal"]["severity"] == "blocking"


def test_codex_preflight_rejects_unsupported_event(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli_main.main(["codex", "preflight", "--event", "pre_tool", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "unsupported_event"


def _healthy_beads() -> BeadsHealth:
    return BeadsHealth(
        ok=True,
        repo_root="/repo",
        beads_dir="/repo/.beads",
        bd_available=True,
        bd_version="bd version 1.0.4",
        initialized=True,
        issue_prefix="dpcx",
        issue_count=10,
        ready_count=1,
        sync_command_available=False,
        warnings=(),
        errors=(),
        recovery_hint=None,
    )
