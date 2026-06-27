from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.providers.beads import (
    BdUnavailableError,
    BeadsNotInitializedError,
    check_beads_health,
    run_bd,
)

SUPPORTED_CODEX_PREFLIGHT_EVENTS = frozenset({"session_start", "stop"})


@dataclass(frozen=True)
class CodexPreflightResult:
    payload: dict[str, Any]
    exit_code: int


# @trace SPEC-70.03
def run_codex_preflight(*, event: str, strict: bool) -> CodexPreflightResult:
    if event not in SUPPORTED_CODEX_PREFLIGHT_EVENTS:
        return CodexPreflightResult(
            payload={
                "command": "codex.preflight",
                "event": event,
                "mode": _mode(strict),
                "ok": False,
                "exit_code": 2,
                "blocking_count": 0,
                "advisory_count": 0,
                "active_issue": None,
                "changed_files": [],
                "evidence": _evidence_summary([]),
                "checks": [],
                "next_commands": [],
                "error": {
                    "code": "unsupported_event",
                    "message": "Supported events are: session_start, stop.",
                },
            },
            exit_code=2,
        )

    checks: list[dict[str, Any]] = []
    next_commands: list[str] = ["dp doctor --json"]

    health = check_beads_health()
    if health.ok:
        checks.append(
            _check(
                "beads_health",
                status="passed",
                severity="blocking",
                message="Beads health is ok.",
                data=health.to_dict(),
            )
        )
    else:
        checks.append(
            _check(
                "beads_health",
                status="failed",
                severity="blocking",
                message="Beads health is not ok; run dp doctor --json.",
                data=health.to_dict(),
            )
        )

    active_issue, active_issue_error = _active_beads_issue()
    if active_issue_error is not None:
        checks.append(
            _check(
                "active_issue",
                status="failed",
                severity="blocking",
                message=active_issue_error,
            )
        )
        next_commands.append("dp task claim --json")
    elif active_issue is None:
        checks.append(
            _check(
                "active_issue",
                status="warning",
                severity="blocking" if strict else "advisory",
                message="No in-progress Beads issue is claimed for this repo.",
            )
        )
        next_commands.append("dp task claim --json")
    else:
        checks.append(
            _check(
                "active_issue",
                status="passed",
                severity="advisory",
                message=f"Active issue: {active_issue['id']}.",
            )
        )

    changed_files, git_error = _git_changed_files()
    if git_error is not None:
        checks.append(
            _check(
                "worktree",
                status="warning",
                severity="advisory",
                message=git_error,
            )
        )
    elif changed_files:
        checks.append(
            _check(
                "worktree",
                status="warning",
                severity="advisory",
                message=f"Working tree has {len(changed_files)} changed file(s).",
            )
        )
        next_commands.append("make check")
    else:
        checks.append(
            _check(
                "worktree",
                status="passed",
                severity="advisory",
                message="Working tree is clean.",
            )
        )

    evidence = _evidence_summary(changed_files)
    if evidence["missing_evidence_signal"]:
        checks.append(
            _check(
                "evidence_signal",
                status="warning",
                severity="blocking" if strict else "advisory",
                message=(
                    "Code or script changes are present without changed tests, docs, or evidence "
                    "artifacts in the working tree."
                ),
            )
        )
        next_commands.append("record evidence with targeted tests or dp verify --goal ... --json")
    else:
        checks.append(
            _check(
                "evidence_signal",
                status="passed",
                severity="advisory",
                message="Working tree includes an evidence signal or has no code/script changes.",
            )
        )

    blocking_count = sum(
        1 for check in checks if check["severity"] == "blocking" and check["status"] != "passed"
    )
    advisory_count = sum(
        1 for check in checks if check["severity"] == "advisory" and check["status"] != "passed"
    )
    exit_code = 0 if blocking_count == 0 else 1
    payload = {
        "command": "codex.preflight",
        "event": event,
        "mode": _mode(strict),
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "blocking_count": blocking_count,
        "advisory_count": advisory_count,
        "active_issue": active_issue,
        "changed_files": changed_files,
        "evidence": evidence,
        "checks": checks,
        "next_commands": _unique(next_commands),
    }
    return CodexPreflightResult(payload=payload, exit_code=exit_code)


def _mode(strict: bool) -> str:
    return "strict" if strict else "guided"


def _check(
    check_id: str,
    *,
    status: str,
    severity: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    check: dict[str, Any] = {
        "id": check_id,
        "status": status,
        "severity": severity,
        "message": message,
    }
    if data is not None:
        check["data"] = data
    return check


def _active_beads_issue() -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = run_bd(
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
        )
    except (BdUnavailableError, BeadsNotInitializedError) as exc:
        return None, str(exc)

    if result.returncode != 0:
        message = result.stderr.strip() or "Unable to list in-progress Beads issues."
        return None, message

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None, "Beads returned malformed JSON for in-progress issues."

    issue = _first_issue(payload)
    if issue is None:
        return None, None

    return (
        {
            "id": _string_or_none(issue.get("id")),
            "title": _string_or_none(issue.get("title")),
            "spec_id": _string_or_none(issue.get("spec_id")),
            "status": _string_or_none(issue.get("status")),
            "issue_type": _string_or_none(issue.get("issue_type")),
            "labels": _string_list(issue.get("labels")),
        },
        None,
    )


def _first_issue(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
    if isinstance(payload, dict):
        if isinstance(payload.get("id"), str):
            return payload
        items = payload.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    return item
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _git_changed_files() -> tuple[list[str], str | None]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        return [], "git command not found; unable to inspect working tree."

    if result.returncode != 0:
        message = result.stderr.strip() or "git status failed; unable to inspect working tree."
        return [], message

    return sorted(_parse_git_status_paths(result.stdout)), None


def _parse_git_status_paths(output: str) -> set[str]:
    paths: set[str] = set()
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if path:
            paths.add(path)
    return paths


def _evidence_summary(changed_files: list[str]) -> dict[str, bool]:
    has_code_changes = any(_is_code_path(path) for path in changed_files)
    has_test_changes = any(path.startswith("tests/") for path in changed_files)
    has_evidence_artifact_changes = any(
        path.startswith(("docs/evidence/", "docs/evidence-runs/")) for path in changed_files
    )
    has_docs_changes = any(
        path.startswith(("docs/", "README.md", "AGENTS.md")) for path in changed_files
    )
    has_verification_signal = has_test_changes or has_evidence_artifact_changes or has_docs_changes
    return {
        "has_code_changes": has_code_changes,
        "has_test_changes": has_test_changes,
        "has_evidence_artifact_changes": has_evidence_artifact_changes,
        "has_docs_changes": has_docs_changes,
        "missing_evidence_signal": has_code_changes and not has_verification_signal,
    }


def _is_code_path(path: str) -> bool:
    path_obj = Path(path)
    return path.startswith(("dp/", "scripts/", "hooks/")) or path_obj.suffix in {
        ".py",
        ".sh",
    }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values
