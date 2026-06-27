from __future__ import annotations

import importlib
import json
from typing import Sequence

import pytest

from dp.providers.beads import (
    BdUnavailableError,
    BeadsHealth,
    BeadsNotInitializedError,
    CommandResult,
)

cli_main = importlib.import_module("dp.cli.main")


@pytest.mark.parametrize(
    ("argv", "expected_command"),
    [
        (["task", "ready"], ["ready"]),
        (["task", "claim"], ["ready", "--claim"]),
        (["task", "claim", "dpcx-egm.1.2"], ["update", "dpcx-egm.1.2", "--claim"]),
        (["task", "show", "dpcx-egm.1.2"], ["show", "dpcx-egm.1.2"]),
        (
            [
                "task",
                "update",
                "dpcx-egm.1.2",
                "--status",
                "in_progress",
                "--priority",
                "1",
                "--owner",
                "alice",
            ],
            [
                "update",
                "dpcx-egm.1.2",
                "--status",
                "in_progress",
                "--priority",
                "P1",
                "--owner",
                "alice",
            ],
        ),
        (
            ["task", "discover", "dpcx-egm.3.1", "Investigate parser drift"],
            [
                "create",
                "Investigate parser drift",
                "--type",
                "task",
                "--deps",
                "discovered-from:dpcx-egm.3.1,blocks:dpcx-egm.3.1",
            ],
        ),
        (
            ["task", "close", "dpcx-egm.1.2", "--reason", "implemented and verified"],
            ["close", "dpcx-egm.1.2", "--reason", "implemented and verified"],
        ),
    ],
)
def test_task_commands_delegate_to_bd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    expected_command: list[str],
) -> None:
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(argv)

    assert exit_code == 0
    assert calls == [expected_command]
    assert capsys.readouterr().out == "ok\n"


def test_task_command_surfaces_bd_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        return CommandResult(returncode=2, stdout="", stderr="simulated failure")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "ready"])

    assert exit_code == 2
    assert "dp task error: simulated failure" in capsys.readouterr().err


def test_task_command_handles_missing_bd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise BdUnavailableError("bd command not found")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "ready"])

    assert exit_code == 127
    assert "dp task error: bd command not found" in capsys.readouterr().err


def test_task_discover_supports_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(returncode=0, stdout="created\n", stderr="")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(
        [
            "task",
            "discover",
            "dpcx-egm.3.1",
            "Add dependency linking docs",
            "--description",
            "Add runbook notes for discover workflow.",
            "--acceptance",
            "Docs include discover command examples.",
            "--priority",
            "P1",
            "--labels",
            "docs,m2",
            "--assignee",
            "alice",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert calls == [
        [
            "create",
            "Add dependency linking docs",
            "--type",
            "task",
            "--deps",
            "discovered-from:dpcx-egm.3.1,blocks:dpcx-egm.3.1",
            "--description",
            "Add runbook notes for discover workflow.",
            "--acceptance",
            "Docs include discover command examples.",
            "--priority",
            "P1",
            "--labels",
            "docs,m2",
            "--assignee",
            "alice",
            "--dry-run",
        ]
    ]
    assert capsys.readouterr().out == "created\n"


def test_task_command_handles_uninitialized_beads(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise BeadsNotInitializedError("No .beads directory found")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "ready"])

    assert exit_code == 2
    assert "dp task error: No .beads directory found" in capsys.readouterr().err


def test_task_command_json_mode_returns_stable_schema(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(returncode=0, stdout='{"items":[{"id":"dpcx-egm.3.3"}]}\n', stderr="")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "ready", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "task.ready"
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert payload["data"] == {"items": [{"id": "dpcx-egm.3.3"}]}
    assert calls == [["ready", "--json"]]


# @trace SPEC-70.02
def test_task_claim_json_claims_ready_work_and_extracts_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []
    issue = {
        "id": "dpcx-ea9.1",
        "title": "M7.2 Add task claim ergonomics and context extraction",
        "spec_id": "SPEC-70.02",
        "description": (
            "Expected files: dp/cli/main.py, dp/providers/beads.py, "
            "tests/unit/test_cli_task.py, docs/runbooks/task-json-output.md. "
            "Do not treat claim/context prose as a repo path."
        ),
        "design": "Prefer a thin wrapper over bd ready --claim --json.",
        "acceptance_criteria": "Tests cover ready-claim and known-id claim.",
        "labels": ["beads", "codex"],
        "parent": "dpcx-ea9",
        "dependencies": [{"id": "dpcx-ea9"}],
        "dependents": [{"issue_id": "dpcx-pb5.19"}],
    }

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(returncode=0, stdout=json.dumps([issue]) + "\n", stderr="")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "claim", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "task.claim"
    assert payload["ok"] is True
    assert payload["beads_command"] == ["ready", "--claim", "--json"]
    assert payload["data"] == [issue]
    context = payload["context"]
    assert context["issue_id"] == "dpcx-ea9.1"
    assert context["title"] == issue["title"]
    assert context["spec_id"] == "SPEC-70.02"
    assert context["labels"] == ["beads", "codex"]
    assert context["dependencies"] == ["dpcx-ea9"]
    assert context["dependents"] == ["dpcx-pb5.19"]
    assert context["read_first"][0] == "docs/specs/SPEC-70-02-task-intake.md"
    assert "dp/cli/main.py" in context["mentioned_paths"]
    assert "tests/unit/test_cli_task.py" in context["mentioned_paths"]
    assert "docs/runbooks/task-json-output.md" in context["mentioned_paths"]
    assert "claim/context" not in context["mentioned_paths"]
    assert context["warnings"] == []
    assert calls == [["ready", "--claim", "--json"]]


def test_task_claim_json_claims_known_issue(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []
    issue = {
        "id": "dpcx-ea9.1",
        "title": "Known issue claim",
        "acceptance_criteria": "Claimed issue has acceptance.",
    }

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        return CommandResult(returncode=0, stdout=json.dumps(issue) + "\n", stderr="")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "claim", "dpcx-ea9.1", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["beads_command"] == ["update", "dpcx-ea9.1", "--claim", "--json"]
    assert payload["context"]["issue_id"] == "dpcx-ea9.1"
    assert calls == [["update", "dpcx-ea9.1", "--claim", "--json"]]


def test_task_claim_json_surfaces_missing_context_guidance(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        return CommandResult(
            returncode=0,
            stdout=json.dumps({"id": "dpcx-blank", "title": "Ambiguous task"}) + "\n",
            stderr="",
        )

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "claim", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context"]["read_first"] == []
    assert payload["context"]["mentioned_paths"] == []
    assert payload["context"]["warnings"] == [
        "Claimed issue does not mention files or a spec id; inspect the issue before editing.",
        "Claimed issue has no acceptance criteria.",
    ]


def test_task_claim_json_handles_missing_bd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise BdUnavailableError("bd command not found")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "claim", "--json"])

    assert exit_code == 127
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "task.claim"
    assert payload["ok"] is False
    assert payload["exit_code"] == 127
    assert payload["error"] == "bd command not found"
    assert payload["beads_command"] == ["ready", "--claim", "--json"]
    assert "context" not in payload


def test_task_claim_json_handles_uninitialized_beads(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise BeadsNotInitializedError("No .beads directory found")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "claim", "dpcx-ea9.1", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "task.claim"
    assert payload["ok"] is False
    assert payload["exit_code"] == 2
    assert payload["error"] == "No .beads directory found"
    assert payload["beads_command"] == ["update", "dpcx-ea9.1", "--claim", "--json"]
    assert "context" not in payload


def test_task_command_json_mode_handles_missing_bd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise BdUnavailableError("bd command not found")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "ready", "--json"])

    assert exit_code == 127
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "task.ready"
    assert payload["ok"] is False
    assert payload["exit_code"] == 127
    assert payload["error"] == "bd command not found"


def test_task_update_rejects_invalid_status_before_invoking_bd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise AssertionError("run_bd should not be called for invalid status")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "update", "dpcx-egm.1.2", "--status", "in_flight"])

    assert exit_code == 2
    assert "Invalid status value 'in_flight'" in capsys.readouterr().err


def test_task_update_rejects_invalid_priority_before_invoking_bd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_bd(_: Sequence[str]) -> CommandResult:
        raise AssertionError("run_bd should not be called for invalid priority")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)

    exit_code = cli_main.main(["task", "update", "dpcx-egm.1.2", "--priority", "P9"])

    assert exit_code == 2
    assert "Invalid priority value 'P9'" in capsys.readouterr().err


def test_doctor_json_returns_stable_beads_health(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main,
        "check_beads_health",
        lambda: BeadsHealth(
            ok=True,
            repo_root="/repo",
            beads_dir="/repo/.beads",
            bd_available=True,
            bd_version="bd version 1.0.4",
            initialized=True,
            issue_prefix="dpcx",
            issue_count=47,
            ready_count=0,
            sync_command_available=False,
            warnings=("bd sync is not available",),
            errors=(),
            recovery_hint=None,
        ),
    )

    exit_code = cli_main.main(["doctor", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["checks"]["beads"]["issue_prefix"] == "dpcx"
    assert payload["checks"]["beads"]["sync_command_available"] is False


def test_doctor_returns_nonzero_with_recovery_hint(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_main,
        "check_beads_health",
        lambda: BeadsHealth(
            ok=False,
            repo_root=None,
            beads_dir=None,
            bd_available=True,
            bd_version="bd version 1.0.4",
            initialized=False,
            issue_prefix=None,
            issue_count=None,
            ready_count=None,
            sync_command_available=False,
            warnings=(),
            errors=("No .beads directory found",),
            recovery_hint="Run `bd bootstrap --dry-run`.",
        ),
    )

    exit_code = cli_main.main(["doctor"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Doctor: FAIL" in captured.out
    assert "No .beads directory found" in captured.err
    assert "bd bootstrap --dry-run" in captured.err
