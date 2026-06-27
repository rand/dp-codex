from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

# @trace SPEC-80.01
SUPPORTED_GOAL_SCHEMA_VERSION = "0.1"
SUPPORTED_GOAL_LEVELS = frozenset({"campaign", "goal", "node", "milestone"})
KNOWN_BLOCKER_ROUTES = frozenset(
    {
        "needs_specification",
        "needs_decision",
        "needs_validator",
        "unsafe_scope",
        "budget_exhausted",
    }
)
KNOWN_BLOCKER_ACTIONS = frozenset(
    {
        "create_spec_stub",
        "create_adr_stub",
        "create_evidence_stub",
        "create_scope_decision",
        "record_progress",
        "create_beads_issue",
    }
)

TRACE_ID_PATTERN = re.compile(r"^(SPEC-\d+(?:\.\d+)?|ADR-\d{4}|GOAL-[A-Za-z0-9][A-Za-z0-9_.-]*)$")
SHELL_CONTROL_PATTERNS = ("&&", "||", ";", "|", "`", "$(", "\n", "\r", ">", "<")
VAGUE_OBJECTIVE_TERMS = frozenset(
    {
        "better",
        "improve",
        "improved",
        "robust",
        "clean",
        "nice",
        "polish",
        "optimize",
        "support",
        "handle",
        "stuff",
        "things",
        "various",
    }
)
SELF_REPORT_TERMS = (
    "agent says",
    "agent reports",
    "codex says",
    "codex reports",
    "self-report",
    "self report",
    "model says",
    "narration",
    "declares it done",
)


@dataclass(frozen=True)
class GoalLintFinding:
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
class GoalLintReport:
    valid: bool
    goal_id: str | None
    errors: tuple[GoalLintFinding, ...]
    warnings: tuple[GoalLintFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "goal_id": self.goal_id,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass(frozen=True)
class GoalLintResult:
    report: GoalLintReport
    exit_code: int


def lint_goal_file(path: Path) -> GoalLintResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _input_error(
            code="missing_file",
            path="$",
            message=f"Goal contract file not found: {path.as_posix()}",
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _input_error(
            code="malformed_json",
            path="$",
            message=f"Goal contract is not valid JSON: line {exc.lineno} column {exc.colno}.",
        )

    return lint_goal_payload(payload)


def lint_goal_payload(payload: Any) -> GoalLintResult:
    if not isinstance(payload, dict):
        return _input_error(
            code="json_object_required",
            path="$",
            message="Goal contract must be a JSON object.",
        )

    goal_id = _non_empty_string(payload.get("id"))
    schema_version = _non_empty_string(payload.get("schema_version"))
    if schema_version != SUPPORTED_GOAL_SCHEMA_VERSION:
        value = schema_version if schema_version is not None else "<missing>"
        return _input_error(
            code="unsupported_schema",
            path="$.schema_version",
            message=(
                f"Unsupported goal schema version {value}. "
                f"Expected {SUPPORTED_GOAL_SCHEMA_VERSION}."
            ),
            goal_id=goal_id,
        )

    errors: list[GoalLintFinding] = []
    warnings: list[GoalLintFinding] = []

    title = _non_empty_string(payload.get("title"))
    level = _non_empty_string(payload.get("level"))
    objective = _non_empty_string(payload.get("objective"))

    if goal_id is None:
        errors.append(
            _finding(
                "missing_id",
                "$.id",
                "Goal must define a non-empty id.",
            )
        )
    if title is None:
        errors.append(
            _finding(
                "missing_title",
                "$.title",
                "Goal must define a non-empty title.",
            )
        )
    if level is None or level not in SUPPORTED_GOAL_LEVELS:
        errors.append(
            _finding(
                "invalid_level",
                "$.level",
                "Goal level must be one of: campaign, goal, milestone, node.",
            )
        )
    if objective is None:
        errors.append(
            _finding(
                "missing_objective",
                "$.objective",
                "Goal must define a non-empty objective.",
            )
        )

    has_evidence = _validate_evidence(payload.get("evidence"), errors, warnings)
    if objective is not None and _objective_is_vague(objective) and not has_evidence:
        errors.append(
            _finding(
                "vague_objective",
                "$.objective",
                "Vague objectives must be paired with measurable evidence.",
            )
        )

    _validate_terminal_states(payload.get("terminal_states"), errors)
    _validate_boundaries(level, payload.get("boundaries"), errors, warnings)
    _validate_blocked_routes(payload.get("blocked_routes"), errors)

    if level == "campaign" and not _non_empty_list(payload.get("nodes")):
        errors.append(
            _finding(
                "campaign_without_nodes",
                "$.nodes",
                "Campaign-level contracts must decompose into non-empty nodes.",
            )
        )

    return GoalLintResult(
        report=GoalLintReport(
            valid=not errors,
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
    goal_id: str | None = None,
) -> GoalLintResult:
    return GoalLintResult(
        report=GoalLintReport(
            valid=False,
            goal_id=goal_id,
            errors=(_finding(code, path, message),),
        ),
        exit_code=2,
    )


def _validate_evidence(
    evidence: Any,
    errors: list[GoalLintFinding],
    warnings: list[GoalLintFinding],
) -> bool:
    if not isinstance(evidence, dict):
        errors.append(
            _finding(
                "missing_evidence",
                "$.evidence",
                "Goal must define evidence with an evidence plan or verification commands.",
            )
        )
        return False

    has_evidence_plan = False
    evidence_plan = _non_empty_string(evidence.get("evidence_plan"))
    if evidence_plan is not None:
        if _is_sane_relative_path(evidence_plan):
            has_evidence_plan = True
        else:
            errors.append(
                _finding(
                    "invalid_evidence_plan_path",
                    "$.evidence.evidence_plan",
                    "Evidence plan path must be a sane relative path.",
                )
            )

    commands = evidence.get("verification_commands")
    has_commands = _non_empty_list(commands)
    if commands is not None and not isinstance(commands, list):
        errors.append(
            _finding(
                "invalid_verification_commands",
                "$.evidence.verification_commands",
                "Verification commands must be a non-empty list when present.",
            )
        )
        has_commands = False

    checks = evidence.get("checks")
    has_checks = _non_empty_list(checks)
    if checks is not None and not isinstance(checks, list):
        errors.append(
            _finding(
                "invalid_evidence_checks",
                "$.evidence.checks",
                "Evidence checks must be a non-empty list when present.",
            )
        )
        has_checks = False

    if not has_evidence_plan and not has_commands and not has_checks:
        errors.append(
            _finding(
                "missing_evidence",
                "$.evidence",
                "Goal must reference an evidence plan or verification commands.",
            )
        )

    trace_ids = evidence.get("trace_ids")
    if trace_ids is not None:
        if not isinstance(trace_ids, list):
            errors.append(
                _finding(
                    "invalid_trace_ids",
                    "$.evidence.trace_ids",
                    "Trace IDs must be a list when present.",
                )
            )
        else:
            for index, trace_id in enumerate(trace_ids):
                if not isinstance(trace_id, str) or TRACE_ID_PATTERN.fullmatch(trace_id) is None:
                    errors.append(
                        _finding(
                            "invalid_trace_id",
                            f"$.evidence.trace_ids[{index}]",
                            "Trace IDs must look like SPEC-70.01, ADR-0001, or GOAL-name.",
                        )
                    )

    _validate_no_raw_shell(evidence, "$.evidence", errors)

    if has_evidence_plan and not has_commands and not has_checks:
        warnings.append(
            _finding(
                "evidence_plan_not_linted_here",
                "$.evidence.evidence_plan",
                "Goal lint validates the reference; "
                "evidence plan contents require dp evidence lint.",
            )
        )

    return has_evidence_plan or has_commands or has_checks


def _validate_terminal_states(terminal_states: Any, errors: list[GoalLintFinding]) -> None:
    if not isinstance(terminal_states, dict):
        errors.append(
            _finding(
                "missing_terminal_states",
                "$.terminal_states",
                "Goal must define terminal states.",
            )
        )
        return

    success = _non_empty_string(terminal_states.get("success"))
    blocked = _non_empty_string(terminal_states.get("blocked"))
    if success is None:
        errors.append(
            _finding(
                "missing_success_terminal",
                "$.terminal_states.success",
                "Goal must define a success terminal state.",
            )
        )
    elif _contains_self_report(success):
        errors.append(
            _finding(
                "self_report_success",
                "$.terminal_states.success",
                "Success cannot depend on agent self-report or narration.",
            )
        )

    if blocked is None:
        errors.append(
            _finding(
                "missing_blocked_terminal",
                "$.terminal_states.blocked",
                "Goal must define a blocked terminal state.",
            )
        )


def _validate_boundaries(
    level: str | None,
    boundaries: Any,
    errors: list[GoalLintFinding],
    warnings: list[GoalLintFinding],
) -> None:
    if level not in {"campaign", "goal", "node"}:
        return

    if not isinstance(boundaries, dict):
        errors.append(
            _finding(
                "missing_boundaries",
                "$.boundaries",
                "Nontrivial goals must define boundaries.",
            )
        )
        return

    boundary_fields = ("read_first", "preferred_paths", "allowed_paths", "allowed_commands")
    has_boundary = any(_non_empty_list(boundaries.get(field)) for field in boundary_fields)
    if not has_boundary:
        errors.append(
            _finding(
                "missing_boundaries",
                "$.boundaries",
                "Nontrivial goals must define at least one boundary field.",
            )
        )

    for field in ("read_first", "preferred_paths", "allowed_paths", "forbidden_paths"):
        value = boundaries.get(field)
        if value is None:
            continue
        if not isinstance(value, list):
            errors.append(
                _finding(
                    "invalid_boundary_paths",
                    f"$.boundaries.{field}",
                    "Boundary path fields must be lists.",
                )
            )
            continue
        for index, item in enumerate(value):
            if not isinstance(item, str) or not _is_sane_relative_path(item):
                errors.append(
                    _finding(
                        "invalid_boundary_path",
                        f"$.boundaries.{field}[{index}]",
                        "Boundary paths must be sane relative paths.",
                    )
                )

    allowed_paths = boundaries.get("allowed_paths")
    if isinstance(allowed_paths, list) and "." in allowed_paths:
        warnings.append(
            _finding(
                "broad_boundary",
                "$.boundaries.allowed_paths",
                "Allowed paths include the repository root.",
            )
        )


def _validate_blocked_routes(blocked_routes: Any, errors: list[GoalLintFinding]) -> None:
    if blocked_routes is None:
        return
    if not isinstance(blocked_routes, dict):
        errors.append(
            _finding(
                "invalid_blocker_routes",
                "$.blocked_routes",
                "Blocked routes must be an object keyed by known route type.",
            )
        )
        return

    for route_type, route in blocked_routes.items():
        route_path = f"$.blocked_routes.{route_type}"
        if route_type not in KNOWN_BLOCKER_ROUTES:
            errors.append(
                _finding(
                    "unknown_blocker_route",
                    route_path,
                    "Blocked route type is not known.",
                )
            )
            continue
        if not isinstance(route, dict):
            errors.append(
                _finding(
                    "invalid_blocker_route",
                    route_path,
                    "Blocked route must be an object.",
                )
            )
            continue
        action = _non_empty_string(route.get("action"))
        if action is None or action not in KNOWN_BLOCKER_ACTIONS:
            errors.append(
                _finding(
                    "unknown_blocker_action",
                    f"{route_path}.action",
                    "Blocked route action is not known.",
                )
            )


def _validate_no_raw_shell(value: Any, path: str, errors: list[GoalLintFinding]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "argv" and not isinstance(child, list):
                errors.append(
                    _finding(
                        "invalid_argv",
                        child_path,
                        "Structured evidence argv fields must be arrays, not shell strings.",
                    )
                )
            _validate_no_raw_shell(child, child_path, errors)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_no_raw_shell(child, f"{path}[{index}]", errors)
        return

    if isinstance(value, str) and any(pattern in value for pattern in SHELL_CONTROL_PATTERNS):
        errors.append(
            _finding(
                "raw_shell_prohibited",
                path,
                "Structured evidence fields must not contain shell control operators.",
            )
        )


def _objective_is_vague(objective: str) -> bool:
    lowered = objective.lower()
    words = set(re.findall(r"[a-z0-9]+", lowered))
    if len(words) <= 3:
        return True
    return any(term in words for term in VAGUE_OBJECTIVE_TERMS)


def _contains_self_report(value: str) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in SELF_REPORT_TERMS)


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


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _finding(code: str, path: str, message: str) -> GoalLintFinding:
    return GoalLintFinding(code=code, path=path, message=message)
