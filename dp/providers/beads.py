from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class BdUnavailableError(RuntimeError):
    pass


class BeadsNotInitializedError(RuntimeError):
    pass


@dataclass(frozen=True)
class BeadsHealth:
    ok: bool
    repo_root: str | None
    beads_dir: str | None
    bd_available: bool
    bd_version: str | None
    initialized: bool
    issue_prefix: str | None
    issue_count: int | None
    ready_count: int | None
    sync_command_available: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    recovery_hint: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "repo_root": self.repo_root,
            "beads_dir": self.beads_dir,
            "bd_available": self.bd_available,
            "bd_version": self.bd_version,
            "initialized": self.initialized,
            "issue_prefix": self.issue_prefix,
            "issue_count": self.issue_count,
            "ready_count": self.ready_count,
            "sync_command_available": self.sync_command_available,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "recovery_hint": self.recovery_hint,
        }


def run_bd(args: Sequence[str]) -> CommandResult:
    _require_beads_context()

    try:
        completed = _run_bd_raw(args)
    except FileNotFoundError as exc:
        raise BdUnavailableError(
            "bd command not found. Install Beads CLI and ensure it is available on PATH."
        ) from exc

    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


# @trace SPEC-70.01
# @trace SPEC-70.07
def check_beads_health() -> BeadsHealth:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = _find_beads_root()
    beads_dir = repo_root / ".beads" if repo_root is not None else None
    recovery_hint: str | None = None

    try:
        version_result = _run_bd_raw(["version"], cwd=repo_root)
    except FileNotFoundError:
        return BeadsHealth(
            ok=False,
            repo_root=repo_root.as_posix() if repo_root is not None else None,
            beads_dir=beads_dir.as_posix() if beads_dir is not None else None,
            bd_available=False,
            bd_version=None,
            initialized=False,
            issue_prefix=None,
            issue_count=None,
            ready_count=None,
            sync_command_available=False,
            warnings=(),
            errors=(
                "bd command not found. Install Beads CLI and ensure it is available on PATH.",
            ),
            recovery_hint="Install Beads, then run `dp doctor --json` again.",
        )

    bd_version = _first_line(version_result.stdout)
    if version_result.returncode != 0:
        errors.append(_command_error("bd version", version_result))

    sync_command_available, sync_absence_expected = _detect_bd_sync_command(
        repo_root=repo_root,
        bd_version=bd_version,
    )
    if not sync_command_available and not sync_absence_expected:
        warnings.append(
            "bd sync is not available in this Beads CLI. Use current Beads "
            "surfaces such as `bd status`, `bd export`, `bd backup`, `bd vc`, "
            "and `bd bootstrap`."
        )

    if repo_root is None:
        errors.append(
            "No .beads directory found in the current path or any parent directory."
        )
        recovery_hint = (
            "Run `bd bootstrap --dry-run` in the repository root. For a new project, "
            "run `bd init --prefix <prefix>`."
        )
        return _health(
            ok=False,
            repo_root=None,
            beads_dir=None,
            bd_available=True,
            bd_version=bd_version,
            initialized=False,
            issue_prefix=None,
            issue_count=None,
            ready_count=None,
            sync_command_available=sync_command_available,
            warnings=warnings,
            errors=errors,
            recovery_hint=recovery_hint,
        )

    assert beads_dir is not None
    readonly_prefix = _readonly_probe_prefix(bd_version)
    context_payload = _run_json_probe(
        [*readonly_prefix, "context", "--json"],
        repo_root,
        _display_command([*readonly_prefix, "context", "--json"]),
        errors,
        warnings,
    )
    if isinstance(context_payload, dict):
        repo_value = context_payload.get("repo_root")
        beads_value = context_payload.get("beads_dir")
        if isinstance(repo_value, str):
            repo_root_text = repo_value
        else:
            repo_root_text = repo_root.as_posix()
        if isinstance(beads_value, str):
            beads_dir_text = beads_value
        else:
            beads_dir_text = beads_dir.as_posix()
    else:
        repo_root_text = repo_root.as_posix()
        beads_dir_text = beads_dir.as_posix()

    issue_prefix = _read_issue_prefix(repo_root, readonly_prefix, errors, warnings)
    status_payload = _run_json_probe(
        [*readonly_prefix, "status", "--json"],
        repo_root,
        _display_command([*readonly_prefix, "status", "--json"]),
        errors,
        warnings,
    )
    issue_count, ready_count = _read_status_counts(status_payload)

    initialized = issue_prefix is not None and status_payload is not None
    if issue_prefix is None:
        recovery_hint = (
            "Beads database is missing issue_prefix config. Run "
            "`bd bootstrap --dry-run`; if it reports an empty local database, "
            "recover with `bd init --reinit-local --prefix <prefix>` and import "
            "the tracked issue snapshot."
        )

    return _health(
        ok=not errors and initialized,
        repo_root=repo_root_text,
        beads_dir=beads_dir_text,
        bd_available=True,
        bd_version=bd_version,
        initialized=initialized,
        issue_prefix=issue_prefix,
        issue_count=issue_count,
        ready_count=ready_count,
        sync_command_available=sync_command_available,
        warnings=warnings,
        errors=errors,
        recovery_hint=recovery_hint,
    )


def _require_beads_context() -> None:
    if _find_beads_root() is not None:
        return

    raise BeadsNotInitializedError(
        "No .beads directory found in the current path. "
        "Run `bd init` at repository root or change into a Beads-initialized workspace."
    )


def _find_beads_root() -> Path | None:
    current = Path.cwd().resolve()

    for candidate in (current, *current.parents):
        beads_dir = candidate / ".beads"
        if beads_dir.is_dir():
            return candidate

    return None


def _run_bd_raw(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bd", *args],
        capture_output=True,
        check=False,
        cwd=cwd,
        text=True,
    )


def _detect_bd_sync_command(
    *,
    repo_root: Path | None,
    bd_version: str | None,
) -> tuple[bool, bool]:
    parsed_version = _parse_bd_version(bd_version)
    if parsed_version is not None and parsed_version >= (1, 0, 0):
        return False, True

    try:
        result = _run_bd_raw(["sync", "--help"], cwd=repo_root)
    except FileNotFoundError:
        return False, False
    return result.returncode == 0, False


def _parse_bd_version(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if match is None:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or "0")
    return major, minor, patch


def _readonly_probe_prefix(bd_version: str | None) -> list[str]:
    parsed_version = _parse_bd_version(bd_version)
    if parsed_version is not None and parsed_version >= (1, 0, 0):
        return ["--readonly", "--sandbox"]
    return ["--readonly"]


def _run_json_probe(
    command: Sequence[str],
    repo_root: Path,
    display_command: str,
    errors: list[str],
    warnings: list[str],
) -> Any | None:
    try:
        result = _run_bd_raw(command, cwd=repo_root)
    except FileNotFoundError:
        errors.append("bd command not found. Install Beads CLI and ensure it is available on PATH.")
        return None

    warnings.extend(_stderr_lines(result.stderr))
    if result.returncode != 0:
        errors.append(_command_error(display_command, result))
        return None

    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        errors.append(f"{display_command} did not return valid JSON: {exc}")
        return None


def _read_issue_prefix(
    repo_root: Path,
    readonly_prefix: Sequence[str],
    errors: list[str],
    warnings: list[str],
) -> str | None:
    payload = _run_json_probe(
        [*readonly_prefix, "config", "get", "issue_prefix", "--json"],
        repo_root,
        _display_command([*readonly_prefix, "config", "get", "issue_prefix", "--json"]),
        errors,
        warnings,
    )
    if not isinstance(payload, dict):
        return None
    value = payload.get("value")
    return value if isinstance(value, str) and value else None


def _read_status_counts(payload: Any | None) -> tuple[int | None, int | None]:
    if not isinstance(payload, dict):
        return None, None
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None, None
    total = summary.get("total_issues")
    ready = summary.get("ready_issues")
    return (
        total if isinstance(total, int) else None,
        ready if isinstance(ready, int) else None,
    )


def _first_line(raw: str) -> str | None:
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _stderr_lines(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _command_error(command: str, result: subprocess.CompletedProcess[str]) -> str:
    detail = result.stderr.strip() or result.stdout.strip() or "command failed"
    return f"{command} failed with exit code {result.returncode}: {detail}"


def _display_command(args: Sequence[str]) -> str:
    return "bd " + " ".join(args)


def _health(
    *,
    ok: bool,
    repo_root: str | None,
    beads_dir: str | None,
    bd_available: bool,
    bd_version: str | None,
    initialized: bool,
    issue_prefix: str | None,
    issue_count: int | None,
    ready_count: int | None,
    sync_command_available: bool,
    warnings: list[str],
    errors: list[str],
    recovery_hint: str | None,
) -> BeadsHealth:
    return BeadsHealth(
        ok=ok,
        repo_root=repo_root,
        beads_dir=beads_dir,
        bd_available=bd_available,
        bd_version=bd_version,
        initialized=initialized,
        issue_prefix=issue_prefix,
        issue_count=issue_count,
        ready_count=ready_count,
        sync_command_available=sync_command_available,
        warnings=tuple(warnings),
        errors=tuple(errors),
        recovery_hint=recovery_hint,
    )
