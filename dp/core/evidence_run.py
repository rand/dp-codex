from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from dp.core.evidence_artifacts import artifact_ref, validate_evidence_output_path
from dp.core.evidence_lint import EvidenceLintReport, lint_evidence_file

# @trace SPEC-80.08
CONTROLLED_ENV_KEYS = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONPATH",
        "TERM",
        "UV_CACHE_DIR",
        "VIRTUAL_ENV",
    }
)


@dataclass(frozen=True)
class EvidenceRunResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class _ProcessOutput:
    exit_code: int
    stdout: str
    stderr: str


def run_evidence_file(
    path: Path,
    *,
    output_path: Path | None = None,
    force: bool = False,
) -> EvidenceRunResult:
    lint_result = lint_evidence_file(path)
    lint_payload = lint_result.report.to_dict()
    output_error = _validate_output_request(path, output_path, force=force)
    if output_error is not None:
        payload = _base_payload(
            lint_result.report,
            evidence_plan_path=path,
            checks=[],
            error=output_error,
        )
        if output_path is not None:
            payload["artifact"] = artifact_ref(output_path, written=False)
        return EvidenceRunResult(payload=payload, exit_code=2)

    if lint_result.exit_code != 0:
        return EvidenceRunResult(
            payload=_base_payload(
                lint_result.report,
                evidence_plan_path=path,
                checks=[],
                error=_error(
                    "invalid_evidence_plan",
                    "$",
                    "Evidence plan failed deterministic lint; no checks were executed.",
                ),
            ),
            exit_code=lint_result.exit_code,
        )

    try:
        payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        return EvidenceRunResult(
            payload={
                "ok": False,
                "command": "evidence.run",
                "evidence_id": lint_payload["evidence_id"],
                "goal_id": lint_payload["goal_id"],
                "evidence_plan": _evidence_plan_source(path),
                "lint": lint_payload,
                "checks": [],
                "summary": _summary([]),
                "error": _error(
                    "input_unavailable",
                    "$",
                    f"Evidence plan could not be loaded after lint: {exc}",
                ),
            },
            exit_code=2,
        )

    check_results = [_run_check(check, index) for index, check in enumerate(payload["checks"])]
    ok = all(check["ok"] is True for check in check_results)
    result_payload = _base_payload(
        lint_result.report,
        evidence_plan_path=path,
        checks=check_results,
        error=None
        if ok
        else _error(
            "evidence_checks_failed",
            "$.checks",
            "One or more evidence checks failed.",
        ),
    )
    exit_code = 0 if ok else 1
    if output_path is not None:
        write_result = _write_output_artifact(result_payload, output_path)
        result_payload = write_result.payload
        exit_code = write_result.exit_code if write_result.exit_code != 0 else exit_code
    return EvidenceRunResult(payload=result_payload, exit_code=exit_code)


def _run_check(check: dict[str, Any], index: int) -> dict[str, Any]:
    check_path = f"$.checks[{index}]"
    argv = cast(list[str], check["argv"])
    cwd_text = cast(str, check.get("cwd", "."))
    timeout = cast(int, check["timeout_seconds"])
    run_cwd = Path.cwd() if cwd_text == "." else Path(cwd_text)

    if not run_cwd.exists() or not run_cwd.is_dir():
        return _check_result(
            check,
            ok=False,
            status="error",
            cwd=cwd_text,
            exit_code=None,
            stdout="",
            stderr="",
            assertions=[],
            error=_error(
                "cwd_not_found",
                f"{check_path}.cwd",
                f"Check cwd does not exist: {cwd_text}",
            ),
        )

    try:
        completed = subprocess.run(
            argv,
            cwd=run_cwd,
            env=_controlled_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _check_result(
            check,
            ok=False,
            status="timed_out",
            cwd=cwd_text,
            exit_code=None,
            stdout="",
            stderr="",
            assertions=[],
            error=_error(
                "timeout",
                f"{check_path}.timeout_seconds",
                f"Check exceeded timeout_seconds={timeout}.",
            ),
        )
    except OSError as exc:
        return _check_result(
            check,
            ok=False,
            status="error",
            cwd=cwd_text,
            exit_code=None,
            stdout="",
            stderr="",
            assertions=[],
            error=_error("process_error", f"{check_path}.argv", f"Check could not run: {exc}"),
        )

    process = _ProcessOutput(
        exit_code=int(completed.returncode),
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    exit_ok = process.exit_code in cast(list[int], check["success_exit_codes"])
    assertion_results = [
        _evaluate_assertion(assertion, index, assertion_index, process, run_cwd)
        for assertion_index, assertion in enumerate(cast(list[dict[str, Any]], check["assertions"]))
    ]
    assertions_ok = all(assertion["ok"] is True for assertion in assertion_results)
    ok = exit_ok and assertions_ok

    if ok:
        status = "passed"
        error = None
    elif not exit_ok:
        status = "failed"
        error = _error(
            "unexpected_exit_code",
            f"{check_path}.success_exit_codes",
            f"Check exited with {process.exit_code}.",
        )
    else:
        status = "failed"
        error = _error("assertion_failed", f"{check_path}.assertions", "A typed assertion failed.")

    return _check_result(
        check,
        ok=ok,
        status=status,
        cwd=cwd_text,
        exit_code=process.exit_code,
        stdout=process.stdout,
        stderr=process.stderr,
        assertions=assertion_results,
        error=error,
    )


def _evaluate_assertion(
    assertion: dict[str, Any],
    check_index: int,
    index: int,
    process: _ProcessOutput,
    cwd: Path,
) -> dict[str, Any]:
    assertion_type = cast(str, assertion["type"])
    path = f"$.checks[{check_index}].assertions[{index}]"

    if assertion_type == "exit_code_in":
        values = cast(list[int], assertion["values"])
        ok = process.exit_code in values
        return _assertion(assertion_type, path, ok, f"Exit code {process.exit_code} in {values}.")

    if assertion_type == "stdout_json":
        ok, _ = _parse_stdout_json(process.stdout)
        message = "stdout is valid JSON." if ok else "stdout is not valid JSON."
        return _assertion(assertion_type, path, ok, message)

    if assertion_type == "json_path_exists":
        json_ok, parsed = _parse_stdout_json(process.stdout)
        target_path = cast(str, assertion["path"])
        ok = json_ok and _json_path_get(parsed, target_path)[0]
        message = (
            f"JSON path exists: {target_path}." if ok else f"JSON path missing: {target_path}."
        )
        return _assertion(assertion_type, path, ok, message)

    if assertion_type == "json_path_equals":
        json_ok, parsed = _parse_stdout_json(process.stdout)
        target_path = cast(str, assertion["path"])
        found, actual = _json_path_get(parsed, target_path) if json_ok else (False, None)
        expected = assertion["value"]
        ok = found and actual == expected
        if ok:
            message = f"JSON path equals expected value: {target_path}."
        else:
            message = f"JSON path {target_path} expected {expected!r}, got {actual!r}."
        return _assertion(assertion_type, path, ok, message)

    if assertion_type == "stdout_contains":
        text = cast(str, assertion["text"])
        ok = text in process.stdout
        message = (
            "stdout contains expected text." if ok else "stdout did not contain expected text."
        )
        return _assertion(assertion_type, path, ok, message)

    if assertion_type == "stderr_empty":
        ok = process.stderr == ""
        message = "stderr is empty." if ok else "stderr is not empty."
        return _assertion(assertion_type, path, ok, message)

    if assertion_type == "file_exists":
        target = cwd / cast(str, assertion["path"])
        ok = target.exists()
        message = (
            f"File exists: {assertion['path']}."
            if ok
            else f"File missing: {assertion['path']}."
        )
        return _assertion(assertion_type, path, ok, message)

    return _assertion(assertion_type, path, False, "Unsupported assertion type.")


def _parse_stdout_json(stdout: str) -> tuple[bool, Any]:
    try:
        return True, json.loads(stdout)
    except json.JSONDecodeError:
        return False, None


def _json_path_get(value: Any, path: str) -> tuple[bool, Any]:
    if path == "$":
        return True, value
    if not path.startswith("$"):
        return False, None

    current = value
    offset = 1
    while offset < len(path):
        if path[offset] == ".":
            offset += 1
            start = offset
            while offset < len(path) and path[offset] not in ".[":
                offset += 1
            key = path[start:offset]
            if not key or not isinstance(current, dict) or key not in current:
                return False, None
            current = current[key]
            continue

        if path[offset] == "[":
            end = path.find("]", offset)
            if end == -1:
                return False, None
            token = path[offset + 1 : end]
            if token.isdigit():
                index = int(token)
                if not isinstance(current, list) or index >= len(current):
                    return False, None
                current = current[index]
            else:
                key = token.strip("\"'")
                if not key or not isinstance(current, dict) or key not in current:
                    return False, None
                current = current[key]
            offset = end + 1
            continue

        return False, None

    return True, current


def _controlled_env() -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in CONTROLLED_ENV_KEYS and isinstance(value, str)
    }
    env.setdefault("PATH", os.defpath)
    return env


def _base_payload(
    lint: EvidenceLintReport,
    *,
    evidence_plan_path: Path,
    checks: list[dict[str, Any]],
    error: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "ok": error is None,
        "command": "evidence.run",
        "evidence_id": lint.evidence_id,
        "goal_id": lint.goal_id,
        "evidence_plan": _evidence_plan_source(evidence_plan_path),
        "lint": lint.to_dict(),
        "checks": checks,
        "summary": _summary(checks),
        "error": error,
        "artifact": None,
    }


def _validate_output_request(
    evidence_plan_path: Path,
    output_path: Path | None,
    *,
    force: bool,
) -> dict[str, str] | None:
    if output_path is None:
        return None
    path_error = validate_evidence_output_path(output_path)
    if path_error is not None:
        return path_error
    if output_path == evidence_plan_path:
        return _error(
            "invalid_output_path",
            "$.output",
            "Evidence run output path must not overwrite the EvidencePlan.",
        )
    if output_path.exists() and not force:
        return _error(
            "output_exists",
            "$.output",
            f"Output path already exists: {output_path.as_posix()}. Use --force to overwrite.",
        )
    if output_path.parent.exists() and not output_path.parent.is_dir():
        return _error(
            "invalid_output_path",
            "$.output",
            f"Output parent is not a directory: {output_path.parent.as_posix()}",
        )
    return None


@dataclass(frozen=True)
class _ArtifactWriteResult:
    payload: dict[str, Any]
    exit_code: int


def _write_output_artifact(payload: dict[str, Any], output_path: Path) -> _ArtifactWriteResult:
    payload = dict(payload)
    payload["artifact"] = artifact_ref(output_path, written=True)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        payload["ok"] = False
        payload["artifact"] = artifact_ref(output_path, written=False)
        payload["error"] = _error(
            "output_write_failed",
            "$.output",
            f"Evidence run output could not be written: {exc}",
        )
        return _ArtifactWriteResult(payload=payload, exit_code=2)
    return _ArtifactWriteResult(payload=payload, exit_code=0)


def _evidence_plan_source(path: Path) -> dict[str, str | None]:
    return {
        "path": path.as_posix(),
        "sha256": _file_sha256(path) if path.exists() else None,
    }


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["status"] == "passed"),
        "failed": sum(1 for check in checks if check["status"] == "failed"),
        "timed_out": sum(1 for check in checks if check["status"] == "timed_out"),
        "errored": sum(1 for check in checks if check["status"] == "error"),
    }


def _check_result(
    check: dict[str, Any],
    *,
    ok: bool,
    status: str,
    cwd: str,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    assertions: list[dict[str, Any]],
    error: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "id": check["id"],
        "ok": ok,
        "status": status,
        "argv": check["argv"],
        "cwd": cwd,
        "timeout_seconds": check["timeout_seconds"],
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "assertions": assertions,
        "error": error,
    }


def _assertion(assertion_type: str, path: str, ok: bool, message: str) -> dict[str, Any]:
    return {
        "type": assertion_type,
        "path": path,
        "ok": ok,
        "message": message,
    }


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "path": path,
        "message": message,
    }
