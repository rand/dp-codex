from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

# @trace SPEC-80.05
SUPPORTED_EVIDENCE_SCHEMA_VERSION = "0.1"
SUPPORTED_CHECK_KINDS = frozenset({"registered_command"})
MUTATION_POLICIES = frozenset({"read_only", "writes_workspace", "writes_event_log"})
ASSERTION_TYPES = frozenset(
    {
        "exit_code_in",
        "file_exists",
        "json_path_equals",
        "json_path_exists",
        "stderr_empty",
        "stdout_contains",
        "stdout_json",
    }
)
SHELL_CONTROL_PATTERNS = ("&&", "||", ";", "|", "`", "$(", "\n", "\r", ">", "<")
EVIDENCE_ID_PATTERN = re.compile(r"^EVIDENCE-[A-Za-z0-9][A-Za-z0-9_.-]*$")
GOAL_ID_PATTERN = re.compile(r"^GOAL-[A-Za-z0-9][A-Za-z0-9_.-]*$")
JSON_PATH_PATTERN = re.compile(r"^\$(?:[.\[][A-Za-z0-9_\"'\\].*|$)")
REGISTERED_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("dp", "agent", "prompt"),
    ("dp", "doctor"),
    ("dp", "enforce", "pre-commit"),
    ("dp", "enforce", "pre-push"),
    ("dp", "evidence", "lint"),
    ("dp", "goal", "block"),
    ("dp", "goal", "claim"),
    ("dp", "goal", "complete"),
    ("dp", "goal", "emit"),
    ("dp", "goal", "heartbeat"),
    ("dp", "goal", "lint"),
    ("dp", "goal", "release"),
    ("dp", "goal", "start"),
    ("dp", "goal", "status"),
    ("dp", "policy", "validate"),
    ("dp", "review"),
    ("dp", "trace", "coverage"),
    ("dp", "trace", "validate"),
    ("dp", "verify"),
    ("make", "check"),
    ("make", "format-check"),
    ("make", "lint"),
    ("make", "test"),
    ("make", "typecheck"),
    ("pytest",),
)
MUTATING_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("dp", "goal", "block"),
    ("dp", "goal", "claim"),
    ("dp", "goal", "complete"),
    ("dp", "goal", "heartbeat"),
    ("dp", "goal", "release"),
    ("dp", "goal", "start"),
)


@dataclass(frozen=True)
class EvidenceLintFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class EvidenceLintReport:
    valid: bool
    evidence_id: str | None
    goal_id: str | None
    errors: tuple[EvidenceLintFinding, ...]
    warnings: tuple[EvidenceLintFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "evidence_id": self.evidence_id,
            "goal_id": self.goal_id,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass(frozen=True)
class EvidenceLintResult:
    report: EvidenceLintReport
    exit_code: int


def lint_evidence_file(path: Path) -> EvidenceLintResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _input_error(
            code="missing_file",
            path="$",
            message=f"Evidence plan file not found: {path.as_posix()}",
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _input_error(
            code="malformed_json",
            path="$",
            message=f"Evidence plan is not valid JSON: line {exc.lineno} column {exc.colno}.",
        )

    return lint_evidence_payload(payload)


def lint_evidence_payload(payload: Any) -> EvidenceLintResult:
    if not isinstance(payload, dict):
        return _input_error(
            code="json_object_required",
            path="$",
            message="Evidence plan must be a JSON object.",
        )

    evidence_id = _non_empty_string(payload.get("id"))
    goal_id = _non_empty_string(payload.get("goal_id"))
    schema_version = _non_empty_string(payload.get("schema_version"))
    if schema_version != SUPPORTED_EVIDENCE_SCHEMA_VERSION:
        value = schema_version if schema_version is not None else "<missing>"
        return _input_error(
            code="unsupported_schema",
            path="$.schema_version",
            message=(
                f"Unsupported evidence schema version {value}. "
                f"Expected {SUPPORTED_EVIDENCE_SCHEMA_VERSION}."
            ),
            evidence_id=evidence_id,
            goal_id=goal_id,
        )

    errors: list[EvidenceLintFinding] = []
    warnings: list[EvidenceLintFinding] = []

    if evidence_id is None:
        errors.append(
            _finding("missing_id", "$.id", "Evidence plan must define a non-empty id.")
        )
    elif EVIDENCE_ID_PATTERN.fullmatch(evidence_id) is None:
        errors.append(
            _finding(
                "invalid_id",
                "$.id",
                "Evidence plan id must look like EVIDENCE-name.",
            )
        )

    if goal_id is None:
        errors.append(
            _finding("missing_goal_id", "$.goal_id", "Evidence plan must define a goal_id.")
        )
    elif GOAL_ID_PATTERN.fullmatch(goal_id) is None:
        errors.append(
            _finding(
                "invalid_goal_id",
                "$.goal_id",
                "Evidence goal_id must look like GOAL-name.",
            )
        )

    _validate_checks(payload.get("checks"), errors, warnings)

    return EvidenceLintResult(
        report=EvidenceLintReport(
            valid=not errors,
            evidence_id=evidence_id,
            goal_id=goal_id,
            errors=tuple(errors),
            warnings=tuple(warnings),
        ),
        exit_code=0 if not errors else 1,
    )


def _input_error(
    *,
    code: str,
    path: str,
    message: str,
    evidence_id: str | None = None,
    goal_id: str | None = None,
) -> EvidenceLintResult:
    return EvidenceLintResult(
        report=EvidenceLintReport(
            valid=False,
            evidence_id=evidence_id,
            goal_id=goal_id,
            errors=(_finding(code, path, message),),
        ),
        exit_code=2,
    )


def _validate_checks(
    checks: Any,
    errors: list[EvidenceLintFinding],
    warnings: list[EvidenceLintFinding],
) -> None:
    if not isinstance(checks, list) or not checks:
        errors.append(
            _finding(
                "missing_checks",
                "$.checks",
                "Evidence plan must define at least one check.",
            )
        )
        return

    seen_ids: set[str] = set()
    for index, check in enumerate(checks):
        check_path = f"$.checks[{index}]"
        if not isinstance(check, dict):
            errors.append(
                _finding("invalid_check", check_path, "Evidence check must be an object.")
            )
            continue

        check_id = _non_empty_string(check.get("id"))
        if check_id is None:
            errors.append(
                _finding(
                    "missing_check_id",
                    f"{check_path}.id",
                    "Evidence check must define a non-empty id.",
                )
            )
        elif check_id in seen_ids:
            errors.append(
                _finding(
                    "duplicate_check_id",
                    f"{check_path}.id",
                    "Evidence check ids must be unique.",
                )
            )
        else:
            seen_ids.add(check_id)

        kind = _non_empty_string(check.get("kind"))
        if kind not in SUPPORTED_CHECK_KINDS:
            errors.append(
                _finding(
                    "unsupported_check_kind",
                    f"{check_path}.kind",
                    "Evidence check kind must be registered_command.",
                )
            )

        argv = check.get("argv")
        argv_values = _validate_argv(argv, f"{check_path}.argv", errors)
        if argv_values is not None:
            _validate_registered_command(argv_values, f"{check_path}.argv", errors)
            _validate_mutation_policy(check, argv_values, check_path, errors)

        _validate_timeout(check.get("timeout_seconds"), check_path, errors)
        _validate_success_exit_codes(check.get("success_exit_codes"), check_path, errors)
        _validate_assertions(check.get("assertions"), check_path, errors)
        _validate_optional_paths(check, check_path, errors)
        _warn_on_large_timeout(check.get("timeout_seconds"), check_path, warnings)


def _validate_argv(
    argv: Any,
    path: str,
    errors: list[EvidenceLintFinding],
) -> tuple[str, ...] | None:
    if not isinstance(argv, list) or not argv:
        errors.append(
            _finding(
                "invalid_argv",
                path,
                "Evidence check argv must be a non-empty array of strings.",
            )
        )
        return None

    values: list[str] = []
    for index, item in enumerate(argv):
        item_path = f"{path}[{index}]"
        item_value = _non_empty_string(item)
        if item_value is None:
            errors.append(
                _finding(
                    "invalid_argv",
                    item_path,
                    "Evidence check argv entries must be non-empty strings.",
                )
            )
            continue
        if _contains_shell_control(item_value):
            errors.append(
                _finding(
                    "raw_shell_prohibited",
                    item_path,
                    "Evidence command argv entries must not contain shell control operators.",
                )
            )
        values.append(item_value)
    return tuple(values)


def _validate_registered_command(
    argv: tuple[str, ...],
    path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    if any(_matches_prefix(argv, prefix) for prefix in REGISTERED_COMMAND_PREFIXES):
        return
    errors.append(
        _finding(
            "unregistered_command",
            path,
            "Evidence command must match a registered command prefix.",
        )
    )


def _validate_mutation_policy(
    check: dict[str, Any],
    argv: tuple[str, ...],
    check_path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    policy = _non_empty_string(check.get("mutation_policy"))
    if policy is None:
        errors.append(
            _finding(
                "missing_mutation_policy",
                f"{check_path}.mutation_policy",
                "Evidence check must declare a mutation_policy.",
            )
        )
        return

    if policy not in MUTATION_POLICIES:
        errors.append(
            _finding(
                "invalid_mutation_policy",
                f"{check_path}.mutation_policy",
                "Mutation policy must be read_only, writes_workspace, or writes_event_log.",
            )
        )
        return

    mutating_command = any(
        _matches_prefix(argv, prefix) for prefix in MUTATING_COMMAND_PREFIXES
    )
    if policy == "read_only" and mutating_command:
        errors.append(
            _finding(
                "invalid_mutation_policy",
                f"{check_path}.mutation_policy",
                "Mutating commands must not declare read_only mutation policy.",
            )
        )


def _validate_timeout(
    timeout: Any,
    check_path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    if timeout is None:
        errors.append(
            _finding(
                "missing_timeout",
                f"{check_path}.timeout_seconds",
                "Evidence check must define timeout_seconds.",
            )
        )
        return
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        errors.append(
            _finding(
                "invalid_timeout",
                f"{check_path}.timeout_seconds",
                "timeout_seconds must be a positive integer.",
            )
        )


def _validate_success_exit_codes(
    exit_codes: Any,
    check_path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    if not isinstance(exit_codes, list) or not exit_codes:
        errors.append(
            _finding(
                "missing_success_exit_codes",
                f"{check_path}.success_exit_codes",
                "Evidence check must define success_exit_codes.",
            )
        )
        return

    for index, exit_code in enumerate(exit_codes):
        if (
            not isinstance(exit_code, int)
            or isinstance(exit_code, bool)
            or not 0 <= exit_code <= 255
        ):
            errors.append(
                _finding(
                    "invalid_success_exit_code",
                    f"{check_path}.success_exit_codes[{index}]",
                    "Success exit codes must be integers from 0 through 255.",
                )
            )


def _validate_assertions(
    assertions: Any,
    check_path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    if not isinstance(assertions, list) or not assertions:
        errors.append(
            _finding(
                "missing_assertions",
                f"{check_path}.assertions",
                "Evidence check must define at least one typed assertion.",
            )
        )
        return

    for index, assertion in enumerate(assertions):
        assertion_path = f"{check_path}.assertions[{index}]"
        if not isinstance(assertion, dict):
            errors.append(
                _finding(
                    "invalid_assertion",
                    assertion_path,
                    "Evidence assertion must be an object.",
                )
            )
            continue
        assertion_type = _non_empty_string(assertion.get("type"))
        if assertion_type not in ASSERTION_TYPES:
            errors.append(
                _finding(
                    "unknown_assertion_type",
                    f"{assertion_path}.type",
                    "Evidence assertion type is not known.",
                )
            )
            continue
        _validate_assertion_shape(assertion, assertion_type, assertion_path, errors)


def _validate_assertion_shape(
    assertion: dict[str, Any],
    assertion_type: str,
    assertion_path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    if assertion_type in {"json_path_exists", "json_path_equals"}:
        path = _non_empty_string(assertion.get("path"))
        if path is None or JSON_PATH_PATTERN.fullmatch(path) is None:
            errors.append(
                _finding(
                    "invalid_json_path",
                    f"{assertion_path}.path",
                    "JSON path assertions must define a path starting with $.",
                )
            )
        if assertion_type == "json_path_equals" and "value" not in assertion:
            errors.append(
                _finding(
                    "missing_assertion_value",
                    f"{assertion_path}.value",
                    "json_path_equals assertions must define value.",
                )
            )
        return

    if assertion_type == "exit_code_in":
        values = assertion.get("values")
        if not isinstance(values, list) or not values:
            errors.append(
                _finding(
                    "missing_assertion_values",
                    f"{assertion_path}.values",
                    "exit_code_in assertions must define values.",
                )
            )
            return
        for index, value in enumerate(values):
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 255:
                errors.append(
                    _finding(
                        "invalid_assertion_exit_code",
                        f"{assertion_path}.values[{index}]",
                        "Assertion exit codes must be integers from 0 through 255.",
                    )
                )
        return

    if assertion_type in {"file_exists"}:
        path = _non_empty_string(assertion.get("path"))
        if path is None or not _is_sane_relative_path(path):
            errors.append(
                _finding(
                    "invalid_assertion_path",
                    f"{assertion_path}.path",
                    "File assertions must define a sane relative path.",
                )
            )
        return

    if assertion_type == "stdout_contains" and _non_empty_string(assertion.get("text")) is None:
        errors.append(
            _finding(
                "missing_assertion_text",
                f"{assertion_path}.text",
                "stdout_contains assertions must define text.",
            )
        )


def _validate_optional_paths(
    check: dict[str, Any],
    check_path: str,
    errors: list[EvidenceLintFinding],
) -> None:
    cwd = check.get("cwd")
    if cwd is not None:
        cwd_value = _non_empty_string(cwd)
        if cwd_value is None or not _is_sane_relative_path(cwd_value):
            errors.append(
                _finding(
                    "invalid_cwd",
                    f"{check_path}.cwd",
                    "Evidence check cwd must be a sane relative path.",
                )
            )


def _warn_on_large_timeout(
    timeout: Any,
    check_path: str,
    warnings: list[EvidenceLintFinding],
) -> None:
    if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout > 1800:
        warnings.append(
            _finding(
                "large_timeout",
                f"{check_path}.timeout_seconds",
                "Timeout is larger than 30 minutes.",
            )
        )


def _matches_prefix(argv: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(argv) >= len(prefix) and argv[: len(prefix)] == prefix


def _contains_shell_control(value: str) -> bool:
    return any(pattern in value for pattern in SHELL_CONTROL_PATTERNS)


def _is_sane_relative_path(value: str) -> bool:
    candidate = value.strip()
    if not candidate or "\x00" in candidate or "\\" in candidate:
        return False
    if candidate.startswith("~") or candidate.startswith("-"):
        return False
    path = PurePosixPath(candidate)
    if path.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _finding(code: str, path: str, message: str) -> EvidenceLintFinding:
    return EvidenceLintFinding(code=code, path=path, message=message)
