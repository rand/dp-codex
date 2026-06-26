from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from dp.providers.beads import BeadsNotInitializedError, check_beads_health, run_bd


def test_run_bd_requires_beads_context(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(BeadsNotInitializedError):
        run_bd(["ready"])


def test_run_bd_works_from_nested_path_with_repo_beads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".beads").mkdir(parents=True)
    nested_workdir = repo_root / "nested" / "path"
    nested_workdir.mkdir(parents=True)
    monkeypatch.chdir(nested_workdir)

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr("dp.providers.beads.subprocess.run", fake_run)

    result = run_bd(["ready"])

    assert calls == [["bd", "ready"]]
    assert result.returncode == 0
    assert result.stdout == "ok\n"


def test_check_beads_health_reports_missing_bd(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr("dp.providers.beads.subprocess.run", fake_run)

    health = check_beads_health()

    assert health.ok is False
    assert health.bd_available is False
    assert health.errors == (
        "bd command not found. Install Beads CLI and ensure it is available on PATH.",
    )


def test_check_beads_health_reports_missing_beads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if command == ["bd", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="bd version 1.0.4\n", stderr="")
        if command == ["bd", "sync", "--help"]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr='Error: unknown command "sync" for "bd"',
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dp.providers.beads.subprocess.run", fake_run)

    health = check_beads_health()

    assert health.ok is False
    assert health.bd_available is True
    assert health.initialized is False
    assert health.sync_command_available is False
    assert "No .beads directory found" in health.errors[0]
    assert health.recovery_hint is not None
    assert "bd bootstrap --dry-run" in health.recovery_hint


def test_check_beads_health_reports_missing_issue_prefix(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".beads").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None = None,
        **_: Any,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd in (None, repo_root)
        if command == ["bd", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="bd version 1.0.4\n", stderr="")
        if command == ["bd", "sync", "--help"]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr='Error: unknown command "sync" for "bd"',
            )
        if command == ["bd", "--readonly", "context", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    '{"repo_root":"'
                    + repo_root.as_posix()
                    + '","beads_dir":"'
                    + (repo_root / ".beads").as_posix()
                    + '"}'
                ),
                stderr="",
            )
        if command == ["bd", "--readonly", "config", "get", "issue_prefix", "--json"]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="issue_prefix config is missing",
            )
        if command == ["bd", "--readonly", "status", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"summary":{"total_issues":0,"ready_issues":0}}',
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dp.providers.beads.subprocess.run", fake_run)

    health = check_beads_health()

    assert health.ok is False
    assert health.initialized is False
    assert health.issue_prefix is None
    assert any("issue_prefix" in error for error in health.errors)
    assert health.recovery_hint is not None
    assert "bd init --reinit-local" in health.recovery_hint


def test_check_beads_health_happy_path_uses_readonly_probes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".beads").mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None = None,
        **_: Any,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd in (None, repo_root)
        calls.append(command)
        if command == ["bd", "version"]:
            return subprocess.CompletedProcess(command, 0, stdout="bd version 1.0.4\n", stderr="")
        if command == ["bd", "sync", "--help"]:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr='Error: unknown command "sync" for "bd"',
            )
        if command == ["bd", "--readonly", "context", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    '{"repo_root":"'
                    + repo_root.as_posix()
                    + '","beads_dir":"'
                    + (repo_root / ".beads").as_posix()
                    + '"}'
                ),
                stderr="",
            )
        if command == ["bd", "--readonly", "config", "get", "issue_prefix", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"key":"issue_prefix","value":"dpcx"}',
                stderr="",
            )
        if command == ["bd", "--readonly", "status", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"summary":{"total_issues":47,"ready_issues":3}}',
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("dp.providers.beads.subprocess.run", fake_run)

    health = check_beads_health()

    assert health.ok is True
    assert health.initialized is True
    assert health.issue_prefix == "dpcx"
    assert health.issue_count == 47
    assert health.ready_count == 3
    assert health.sync_command_available is False
    assert calls == [
        ["bd", "version"],
        ["bd", "sync", "--help"],
        ["bd", "--readonly", "context", "--json"],
        ["bd", "--readonly", "config", "get", "issue_prefix", "--json"],
        ["bd", "--readonly", "status", "--json"],
    ]
