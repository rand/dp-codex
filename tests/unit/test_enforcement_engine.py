from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dp.enforcement.engine import run_enforcement


def _write_policy(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_result(
    returncode: int,
    *,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_enforcement_pre_commit_passes_when_checks_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    policy_path = tmp_path / "policy.json"
    _write_policy(policy_path, {"mode": "strict"})

    command_results: dict[tuple[str, ...], subprocess.CompletedProcess[str]] = {
        ("make", "lint"): _build_result(0),
        ("make", "typecheck"): _build_result(0),
        ("make", "test"): _build_result(0),
        (
            "uv",
            "run",
            "dp",
            "trace",
            "validate",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
            "--trace-glob",
            "scripts/**/*.py",
        ): _build_result(0),
        (
            "uv",
            "run",
            "dp",
            "trace",
            "coverage",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
            "--trace-glob",
            "scripts/**/*.py",
        ): _build_result(
            0,
            stdout=json.dumps(
                {
                    "total_specs": 2,
                    "covered_count": 2,
                    "covered_specs": ["SPEC-01.01", "SPEC-01.02"],
                    "uncovered_specs": [],
                }
            ),
        ),
    }

    def fake_run(
        cmd: list[str],
        *,
        capture_output: bool,
        check: bool,
        cwd: Path,
        env: dict[str, str],
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert check is False
        assert text is True
        assert cwd == tmp_path
        assert env["UV_CACHE_DIR"] == (tmp_path / ".uv-cache").as_posix()
        key = tuple(cmd)
        if key not in command_results:
            raise AssertionError(f"Unexpected command: {cmd}")
        return command_results[key]

    monkeypatch.setattr("dp.enforcement.engine.subprocess.run", fake_run)

    report = run_enforcement(stage="pre-commit", policy_path=policy_path, repo_root=tmp_path)

    assert report.blocked is False
    assert report.bypassed is False
    assert [item.check for item in report.checks] == [
        "lint",
        "typecheck",
        "tests",
        "trace_validate",
        "trace_coverage",
    ]
    assert all(item.status == "passed" for item in report.checks)


def test_run_enforcement_pre_commit_blocks_when_trace_coverage_has_gaps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    policy_path = tmp_path / "policy.json"
    _write_policy(policy_path, {"mode": "strict"})

    command_results: dict[tuple[str, ...], subprocess.CompletedProcess[str]] = {
        ("make", "lint"): _build_result(0),
        ("make", "typecheck"): _build_result(0),
        ("make", "test"): _build_result(0),
        (
            "uv",
            "run",
            "dp",
            "trace",
            "validate",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
            "--trace-glob",
            "scripts/**/*.py",
        ): _build_result(0),
        (
            "uv",
            "run",
            "dp",
            "trace",
            "coverage",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
            "--trace-glob",
            "scripts/**/*.py",
        ): _build_result(
            0,
            stdout=json.dumps(
                {
                    "total_specs": 2,
                    "covered_count": 1,
                    "covered_specs": ["SPEC-01.01"],
                    "uncovered_specs": ["SPEC-01.02"],
                }
            ),
        ),
    }

    def fake_run(
        cmd: list[str],
        *,
        capture_output: bool,
        check: bool,
        cwd: Path,
        env: dict[str, str],
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert check is False
        assert text is True
        assert cwd == tmp_path
        assert env["UV_CACHE_DIR"] == (tmp_path / ".uv-cache").as_posix()
        key = tuple(cmd)
        if key not in command_results:
            raise AssertionError(f"Unexpected command: {cmd}")
        return command_results[key]

    monkeypatch.setattr("dp.enforcement.engine.subprocess.run", fake_run)

    report = run_enforcement(stage="pre-commit", policy_path=policy_path, repo_root=tmp_path)

    assert report.blocked is True
    by_check = {item.check: item for item in report.checks}
    assert by_check["trace_coverage"].status == "failed"
    assert "uncovered spec" in by_check["trace_coverage"].message


def test_run_enforcement_pre_push_respects_policy_disabled_checks(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    _write_policy(policy_path, {"mode": "guided"})

    report = run_enforcement(stage="pre-push", policy_path=policy_path, repo_root=tmp_path)

    assert report.blocked is False
    assert [item.check for item in report.checks] == ["task_sync", "review", "verify"]
    assert all(item.status == "skipped" for item in report.checks)
    assert all(item.message == "Disabled by policy." for item in report.checks)


def test_run_enforcement_records_bypass_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_path = tmp_path / "policy.json"
    _write_policy(policy_path, {"mode": "guided"})

    monkeypatch.setenv("DP_BYPASS_ENFORCEMENT", "1")
    monkeypatch.setenv("DP_BYPASS_REASON", "hotfix rollback")
    monkeypatch.setenv("USER", "ci-user")

    report = run_enforcement(stage="pre-push", policy_path=policy_path, repo_root=tmp_path)

    assert report.bypassed is True
    assert report.blocked is False
    assert report.bypass_reason == "hotfix rollback"
    assert report.checks == ()

    log_path = tmp_path / ".dp" / "bypass-log.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["stage"] == "pre-push"
    assert payload["reason"] == "hotfix rollback"
    assert payload["actor"] == "ci-user"
