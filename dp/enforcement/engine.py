from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dp.core.policy import PolicyConfig, load_policy_config

Stage = Literal["pre-commit", "pre-push"]
CheckStatus = Literal["passed", "failed", "skipped"]

PRE_COMMIT_CHECK_ORDER = (
    "lint",
    "typecheck",
    "tests",
    "trace_validate",
    "trace_coverage",
)
PRE_PUSH_CHECK_ORDER = (
    "task_health",
    "review",
    "verify",
)

ENFORCEMENT_SPEC_GLOB = "docs/specs/**/*.md"
ENFORCEMENT_TRACE_GLOB_PRIMARY = "dp/**/*.py"
ENFORCEMENT_TRACE_GLOB_SECONDARY = "scripts/**/*.py"

CHECK_COMMANDS = {
    "lint": ("make", "lint"),
    "typecheck": ("make", "typecheck"),
    "tests": ("make", "test"),
    "trace_validate": (
        "uv",
        "run",
        "dp",
        "trace",
        "validate",
        "--json",
        "--spec-glob",
        ENFORCEMENT_SPEC_GLOB,
        "--trace-glob",
        ENFORCEMENT_TRACE_GLOB_PRIMARY,
        "--trace-glob",
        ENFORCEMENT_TRACE_GLOB_SECONDARY,
    ),
    "trace_coverage": (
        "uv",
        "run",
        "dp",
        "trace",
        "coverage",
        "--json",
        "--spec-glob",
        ENFORCEMENT_SPEC_GLOB,
        "--trace-glob",
        ENFORCEMENT_TRACE_GLOB_PRIMARY,
        "--trace-glob",
        ENFORCEMENT_TRACE_GLOB_SECONDARY,
    ),
    "task_health": ("uv", "run", "dp", "doctor", "--json"),
    "review": ("uv", "run", "dp", "review", "--json"),
    "verify": ("uv", "run", "dp", "verify", "--json"),
}


@dataclass(frozen=True)
class EnforcementCheckResult:
    check: str
    status: CheckStatus
    blocking: bool
    command: str | None
    exit_code: int | None
    duration_seconds: float
    message: str

    def to_dict(self) -> dict[str, str | bool | int | float | None]:
        return {
            "check": self.check,
            "status": self.status,
            "blocking": self.blocking,
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 3),
            "message": self.message,
        }


@dataclass(frozen=True)
class EnforcementReport:
    stage: Stage
    mode: str
    policy_path: str
    bypassed: bool
    bypass_reason: str | None
    blocked: bool
    checks: tuple[EnforcementCheckResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "mode": self.mode,
            "policy_path": self.policy_path,
            "bypassed": self.bypassed,
            "bypass_reason": self.bypass_reason,
            "blocked": self.blocked,
            "checks": [check.to_dict() for check in self.checks],
        }


def run_enforcement(stage: Stage, policy_path: Path, repo_root: Path) -> EnforcementReport:
    policy = load_policy_config(policy_path)

    bypass_reason = _read_bypass_reason()
    if bypass_reason is not None:
        _record_bypass(stage=stage, reason=bypass_reason, repo_root=repo_root)
        return EnforcementReport(
            stage=stage,
            mode=policy.mode,
            policy_path=policy_path.as_posix(),
            bypassed=True,
            bypass_reason=bypass_reason,
            blocked=False,
            checks=(),
        )

    checks: list[EnforcementCheckResult] = []
    for check_name in _checks_for_stage(stage):
        checks.append(_run_one_check(check_name, policy, repo_root))

    blocked = any(check.status == "failed" and check.blocking for check in checks)
    return EnforcementReport(
        stage=stage,
        mode=policy.mode,
        policy_path=policy_path.as_posix(),
        bypassed=False,
        bypass_reason=None,
        blocked=blocked,
        checks=tuple(checks),
    )


def _checks_for_stage(stage: Stage) -> tuple[str, ...]:
    if stage == "pre-commit":
        return PRE_COMMIT_CHECK_ORDER
    if stage == "pre-push":
        return PRE_PUSH_CHECK_ORDER
    raise ValueError(f"Unsupported enforcement stage: {stage}")


def _run_one_check(
    check_name: str,
    policy: PolicyConfig,
    repo_root: Path,
) -> EnforcementCheckResult:
    blocking = bool(policy.checks.get(check_name, False))
    if not blocking:
        return EnforcementCheckResult(
            check=check_name,
            status="skipped",
            blocking=False,
            command=None,
            exit_code=None,
            duration_seconds=0.0,
            message="Disabled by policy.",
        )

    command = CHECK_COMMANDS[check_name]
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", (repo_root / ".uv-cache").as_posix())
    start = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            check=False,
            cwd=repo_root,
            env=env,
            text=True,
        )
    except FileNotFoundError as exc:
        duration = time.monotonic() - start
        return EnforcementCheckResult(
            check=check_name,
            status="failed",
            blocking=True,
            command=shlex.join(command),
            exit_code=127,
            duration_seconds=duration,
            message=f"Required command not found: {exc.filename}",
        )

    duration = time.monotonic() - start
    passed, message = _evaluate_check_result(
        check_name=check_name,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if passed:
        return EnforcementCheckResult(
            check=check_name,
            status="passed",
            blocking=True,
            command=shlex.join(command),
            exit_code=0,
            duration_seconds=duration,
            message=message,
        )

    return EnforcementCheckResult(
        check=check_name,
        status="failed",
        blocking=True,
        command=shlex.join(command),
        exit_code=completed.returncode,
        duration_seconds=duration,
        message=message.splitlines()[0],
    )


def _evaluate_check_result(
    *,
    check_name: str,
    return_code: int,
    stdout: str,
    stderr: str,
) -> tuple[bool, str]:
    if return_code != 0:
        return False, stderr.strip() or stdout.strip() or "Check failed."

    if check_name != "trace_coverage":
        return True, "Check passed."

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return False, "trace_coverage must emit JSON output for enforcement."
    if not isinstance(payload, dict):
        return False, "trace_coverage output payload must be a JSON object."

    uncovered = payload.get("uncovered_specs", [])
    if not isinstance(uncovered, list):
        return False, "trace_coverage output is missing uncovered_specs list."

    uncovered_ids = [value for value in uncovered if isinstance(value, str)]
    if uncovered_ids:
        preview = ", ".join(uncovered_ids[:3])
        suffix = " ..." if len(uncovered_ids) > 3 else ""
        return (
            False,
            f"Trace coverage failed: {len(uncovered_ids)} uncovered spec(s): {preview}{suffix}",
        )

    covered_count = payload.get("covered_count")
    total_specs = payload.get("total_specs")
    if isinstance(covered_count, int) and isinstance(total_specs, int):
        return True, f"Trace coverage passed ({covered_count}/{total_specs} covered)."

    return True, "Trace coverage passed."


def _read_bypass_reason() -> str | None:
    if os.environ.get("DP_BYPASS_ENFORCEMENT", "").strip().lower() not in {"1", "true", "yes"}:
        return None

    reason = os.environ.get("DP_BYPASS_REASON", "").strip()
    if not reason:
        return "Bypass requested without DP_BYPASS_REASON."
    return reason


def _record_bypass(stage: Stage, reason: str, repo_root: Path) -> None:
    log_dir = repo_root / ".dp"
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "stage": stage,
        "reason": reason,
        "actor": os.environ.get("USER", "unknown"),
    }
    with (log_dir / "bypass-log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
