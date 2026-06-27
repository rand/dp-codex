from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from dp.core.goal_emit import emit_goal_prompt
from dp.core.goal_lint import lint_goal_file
from dp.core.goal_state import (
    DEFAULT_GOAL_EVENT_LOG,
    GoalState,
    claim_goal,
    reconstruct_goal_state,
)

# @trace SPEC-80.04
SUPPORTED_LOOP_SCHEMA_VERSION = "0.1"
LOOP_ID_PATTERN = re.compile(r"^LOOP-[A-Za-z0-9][A-Za-z0-9_.-]*$")
GOAL_ID_PATTERN = re.compile(r"^GOAL-[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True)
class LoopLintFinding:
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
class LoopLintReport:
    valid: bool
    loop_id: str | None
    errors: tuple[LoopLintFinding, ...]
    warnings: tuple[LoopLintFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "loop_id": self.loop_id,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass(frozen=True)
class LoopLintResult:
    report: LoopLintReport
    exit_code: int


@dataclass(frozen=True)
class LoopCommandResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class LoopNode:
    node_id: str
    goal_id: str
    goal_path: Path
    depends_on: tuple[str, ...]
    beads_issue_id: str | None
    evidence_plan: str | None


@dataclass(frozen=True)
class LoopContract:
    loop_id: str
    title: str
    nodes: tuple[LoopNode, ...]


@dataclass(frozen=True)
class LoopValidation:
    contract: LoopContract | None
    result: LoopLintResult


def lint_loop_file(path: Path) -> LoopLintResult:
    return _validate_loop_file(path).result


def loop_status(
    loop_path: Path,
    *,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> LoopCommandResult:
    validation = _validate_loop_file(loop_path)
    if validation.result.exit_code != 0 or validation.contract is None:
        return _lint_failure_payload("loop.status", validation.result)

    node_states = _node_statuses(validation.contract, event_log=event_log)
    ready_node_ids = [node.node_id for node in node_states if node.state == "ready"]
    blocked_node_ids = [node.node_id for node in node_states if node.state == "blocked"]
    claimed_node_ids = [
        node.node_id
        for node in node_states
        if node.state in {"claimed", "started", "pursuing"}
    ]
    verified_node_ids = [node.node_id for node in node_states if node.state == "verified"]
    payload = {
        "ok": True,
        "command": "loop.status",
        "loop_id": validation.contract.loop_id,
        "nodes": [node.to_dict() for node in node_states],
        "ready_node_ids": ready_node_ids,
        "blocked_node_ids": blocked_node_ids,
        "claimed_node_ids": claimed_node_ids,
        "verified_node_ids": verified_node_ids,
    }
    payload["summary"] = {
        "total": len(node_states),
        "ready": len(ready_node_ids),
        "blocked": len(blocked_node_ids),
        "claimed": len(claimed_node_ids),
        "verified": len(verified_node_ids),
    }
    return LoopCommandResult(payload=payload, exit_code=0)


def loop_next(
    loop_path: Path,
    *,
    claim: bool,
    emit_format: str | None,
    agent: str,
    lease: str,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> LoopCommandResult:
    if emit_format is not None and emit_format != "codex":
        return _usage_error(
            "loop.next",
            "unsupported_emit_format",
            "$.emit",
            "Only codex emit format is supported.",
        )
    if claim and not agent.strip():
        return _usage_error("loop.next", "agent_required", "$.agent", "Agent must be non-empty.")

    validation = _validate_loop_file(loop_path)
    if validation.result.exit_code != 0 or validation.contract is None:
        return _lint_failure_payload("loop.next", validation.result)

    node_states = _node_statuses(validation.contract, event_log=event_log)
    next_node_state = next(
        (node for node in node_states if node.state == "ready"),
        None,
    )
    if next_node_state is None:
        payload = {
            "ok": False,
            "command": "loop.next",
            "loop_id": validation.contract.loop_id,
            "error": {
                "code": "no_ready_goal",
                "message": "No ready unclaimed loop node is available.",
            },
            "ready_node_ids": [],
            "blocked_node_ids": [
                node.node_id for node in node_states if node.state == "blocked"
            ],
            "nodes": [node.to_dict() for node in node_states],
        }
        return LoopCommandResult(payload=payload, exit_code=1)

    selected_node = next_node_state.node
    active_state = next_node_state.goal_state
    claim_payload: dict[str, Any] | None = None
    if claim:
        claim_result = claim_goal(
            selected_node.goal_path,
            agent=agent,
            lease=lease,
            event_log=event_log,
        )
        if claim_result.exit_code != 0:
            return LoopCommandResult(
                payload={
                    "ok": False,
                    "command": "loop.next",
                    "loop_id": validation.contract.loop_id,
                    "node_id": selected_node.node_id,
                    "goal_id": selected_node.goal_id,
                    "error": {
                        "code": "goal_claim_failed",
                        "message": "Ready goal could not be claimed.",
                    },
                    "claim": claim_result.payload,
                },
                exit_code=claim_result.exit_code,
            )
        claim_payload = claim_result.payload
        active_state = reconstruct_goal_state(
            goal_id=selected_node.goal_id,
            goal_path=selected_node.goal_path,
            event_log=event_log,
        )

    goal_contract = _read_goal_contract(selected_node.goal_path)
    package = _goal_package(
        loop_id=validation.contract.loop_id,
        node=selected_node,
        goal_contract=goal_contract,
        goal_state=active_state,
        command="loop.next",
    )
    if claim_payload is not None and "event_log" in claim_payload:
        package["event_log"] = claim_payload["event_log"]

    if emit_format == "codex":
        emit_result = emit_goal_prompt(selected_node.goal_path, output_format=emit_format)
        if emit_result.exit_code != 0:
            return LoopCommandResult(
                payload={
                    "ok": False,
                    "command": "loop.next",
                    "loop_id": validation.contract.loop_id,
                    "node_id": selected_node.node_id,
                    "goal_id": selected_node.goal_id,
                    "emit": emit_result.payload,
                },
                exit_code=emit_result.exit_code,
            )
        package["codex_goal"] = emit_result.payload.get("codex_goal")
        package["format"] = "codex"

    return LoopCommandResult(payload=package, exit_code=0)


@dataclass(frozen=True)
class LoopNodeStatus:
    node: LoopNode
    state: str
    goal_state: GoalState
    unmet_dependencies: tuple[str, ...]

    @property
    def node_id(self) -> str:
        return self.node.node_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node.node_id,
            "goal_id": self.node.goal_id,
            "goal_path": self.node.goal_path.as_posix(),
            "beads_issue_id": self.node.beads_issue_id,
            "depends_on": list(self.node.depends_on),
            "unmet_dependencies": list(self.unmet_dependencies),
            "state": self.state,
            "goal_state": self.goal_state.state,
            "lease": self.goal_state.lease,
            "blocked": self.goal_state.blocked,
            "last_event": self.goal_state.last_event,
            "evidence_plan": self.node.evidence_plan,
        }


def _validate_loop_file(path: Path) -> LoopValidation:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result = _input_error(
            code="missing_file",
            path="$",
            message=f"Loop ledger file not found: {path.as_posix()}",
        )
        return LoopValidation(contract=None, result=result)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        result = _input_error(
            code="malformed_json",
            path="$",
            message=f"Loop ledger is not valid JSON: line {exc.lineno} column {exc.colno}.",
        )
        return LoopValidation(contract=None, result=result)

    return _validate_loop_payload(payload)


def _validate_loop_payload(payload: Any) -> LoopValidation:
    if not isinstance(payload, dict):
        return LoopValidation(
            contract=None,
            result=_input_error(
                code="json_object_required",
                path="$",
                message="Loop ledger must be a JSON object.",
            ),
        )

    loop_id = _non_empty_string(payload.get("id"))
    schema_version = _non_empty_string(payload.get("schema_version"))
    if schema_version != SUPPORTED_LOOP_SCHEMA_VERSION:
        value = schema_version if schema_version is not None else "<missing>"
        return LoopValidation(
            contract=None,
            result=_input_error(
                code="unsupported_schema",
                path="$.schema_version",
                message=(
                    f"Unsupported loop schema version {value}. "
                    f"Expected {SUPPORTED_LOOP_SCHEMA_VERSION}."
                ),
                loop_id=loop_id,
            ),
        )

    errors: list[LoopLintFinding] = []
    warnings: list[LoopLintFinding] = []
    title = _non_empty_string(payload.get("title"))

    if loop_id is None:
        errors.append(_finding("missing_id", "$.id", "Loop ledger must define an id."))
    elif LOOP_ID_PATTERN.fullmatch(loop_id) is None:
        errors.append(
            _finding("invalid_id", "$.id", "Loop ledger id must look like LOOP-name.")
        )
    if title is None:
        errors.append(
            _finding("missing_title", "$.title", "Loop ledger must define a title.")
        )

    nodes = _validate_nodes(payload.get("nodes"), errors, warnings)
    _validate_dependencies(nodes, errors)

    contract: LoopContract | None = None
    if not errors and loop_id is not None and title is not None:
        contract = LoopContract(loop_id=loop_id, title=title, nodes=tuple(nodes))

    return LoopValidation(
        contract=contract,
        result=LoopLintResult(
            report=LoopLintReport(
                valid=not errors,
                loop_id=loop_id,
                errors=tuple(errors),
                warnings=tuple(warnings),
            ),
            exit_code=0 if not errors else 1,
        ),
    )


def _validate_nodes(
    nodes_value: Any,
    errors: list[LoopLintFinding],
    warnings: list[LoopLintFinding],
) -> list[LoopNode]:
    if not isinstance(nodes_value, list) or not nodes_value:
        errors.append(
            _finding(
                "missing_nodes",
                "$.nodes",
                "Loop ledger must define at least one node.",
            )
        )
        return []

    nodes: list[LoopNode] = []
    seen_node_ids: set[str] = set()
    seen_goal_ids: set[str] = set()
    for index, node_value in enumerate(nodes_value):
        node_path = f"$.nodes[{index}]"
        if not isinstance(node_value, dict):
            errors.append(_finding("invalid_node", node_path, "Loop node must be an object."))
            continue

        kind = _non_empty_string(node_value.get("kind"))
        if kind is not None and kind != "goal":
            errors.append(
                _finding(
                    "unsupported_node_kind",
                    f"{node_path}.kind",
                    "Only goal nodes are supported.",
                )
            )

        node_id = _non_empty_string(node_value.get("id"))
        goal_id = _non_empty_string(node_value.get("goal_id"))
        goal_path_value = _non_empty_string(node_value.get("goal_path"))
        depends_on = _string_list(node_value.get("depends_on"))
        beads_issue_id = _non_empty_string(node_value.get("beads_issue_id"))
        evidence_plan = _non_empty_string(node_value.get("evidence_plan"))

        if node_id is None:
            errors.append(
                _finding("missing_node_id", f"{node_path}.id", "Loop node must define an id.")
            )
        elif node_id in seen_node_ids:
            errors.append(
                _finding(
                    "duplicate_node_id",
                    f"{node_path}.id",
                    "Loop node ids must be unique.",
                )
            )
        else:
            seen_node_ids.add(node_id)

        if goal_id is None:
            errors.append(
                _finding(
                    "missing_goal_id",
                    f"{node_path}.goal_id",
                    "Loop node must define a goal_id.",
                )
            )
        elif GOAL_ID_PATTERN.fullmatch(goal_id) is None:
            errors.append(
                _finding(
                    "invalid_goal_id",
                    f"{node_path}.goal_id",
                    "Loop node goal_id must look like GOAL-name.",
                )
            )
        elif goal_id in seen_goal_ids:
            errors.append(
                _finding(
                    "duplicate_goal_id",
                    f"{node_path}.goal_id",
                    "Loop node goal_ids must be unique.",
                )
            )
        else:
            seen_goal_ids.add(goal_id)

        if depends_on is None:
            errors.append(
                _finding(
                    "invalid_depends_on",
                    f"{node_path}.depends_on",
                    "Loop node depends_on must be an array of node ids.",
                )
            )
            depends_on_values: tuple[str, ...] = ()
        else:
            depends_on_values = tuple(depends_on)

        if goal_path_value is None:
            errors.append(
                _finding(
                    "missing_goal_path",
                    f"{node_path}.goal_path",
                    "Loop node must define goal_path.",
                )
            )
            goal_path = Path("")
        elif not _is_sane_relative_path(goal_path_value):
            errors.append(
                _finding(
                    "invalid_goal_path",
                    f"{node_path}.goal_path",
                    "Loop node goal_path must be a sane relative path.",
                )
            )
            goal_path = Path(goal_path_value)
        else:
            goal_path = Path(goal_path_value)
            _validate_goal_reference(goal_path, goal_id, node_path, errors)

        if evidence_plan is not None and not _is_sane_relative_path(evidence_plan):
            errors.append(
                _finding(
                    "invalid_evidence_plan_path",
                    f"{node_path}.evidence_plan",
                    "Loop node evidence_plan must be a sane relative path.",
                )
            )

        if node_id is not None and goal_id is not None and goal_path_value is not None:
            nodes.append(
                LoopNode(
                    node_id=node_id,
                    goal_id=goal_id,
                    goal_path=goal_path,
                    depends_on=depends_on_values,
                    beads_issue_id=beads_issue_id,
                    evidence_plan=evidence_plan,
                )
            )

    return nodes


def _validate_goal_reference(
    goal_path: Path,
    expected_goal_id: str | None,
    node_path: str,
    errors: list[LoopLintFinding],
) -> None:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        errors.append(
            _finding(
                "invalid_goal_contract",
                f"{node_path}.goal_path",
                "Loop node goal_path must reference a valid GoalContract.",
            )
        )
        return
    if (
        expected_goal_id is not None
        and lint_result.report.goal_id is not None
        and lint_result.report.goal_id != expected_goal_id
    ):
        errors.append(
            _finding(
                "goal_id_mismatch",
                f"{node_path}.goal_id",
                "Loop node goal_id must match the referenced GoalContract id.",
            )
        )


def _validate_dependencies(nodes: list[LoopNode], errors: list[LoopLintFinding]) -> None:
    node_ids = {node.node_id for node in nodes}
    for index, node in enumerate(nodes):
        for dependency in node.depends_on:
            if dependency not in node_ids:
                errors.append(
                    _finding(
                        "unknown_dependency",
                        f"$.nodes[{index}].depends_on",
                        f"Loop node dependency does not resolve: {dependency}.",
                    )
                )
    if _has_cycle(nodes):
        errors.append(
            _finding(
                "dependency_cycle",
                "$.nodes",
                "Loop node dependencies must be acyclic.",
            )
        )


def _has_cycle(nodes: list[LoopNode]) -> bool:
    graph = {node.node_id: set(node.depends_on) for node in nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visited:
            return False
        if node_id in visiting:
            return True
        visiting.add(node_id)
        for dependency in graph.get(node_id, set()):
            if dependency in graph and visit(dependency):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in graph)


def _node_statuses(
    contract: LoopContract,
    *,
    event_log: Path,
) -> tuple[LoopNodeStatus, ...]:
    goal_states = {
        node.node_id: reconstruct_goal_state(
            goal_id=node.goal_id,
            goal_path=node.goal_path,
            event_log=event_log,
        )
        for node in contract.nodes
    }
    statuses: list[LoopNodeStatus] = []
    for node in contract.nodes:
        unmet_dependencies = tuple(
            dependency
            for dependency in node.depends_on
            if goal_states[dependency].state != "verified"
        )
        state = _derive_node_state(goal_states[node.node_id], unmet_dependencies)
        statuses.append(
            LoopNodeStatus(
                node=node,
                state=state,
                goal_state=goal_states[node.node_id],
                unmet_dependencies=unmet_dependencies,
            )
        )
    return tuple(statuses)


def _derive_node_state(goal_state: GoalState, unmet_dependencies: tuple[str, ...]) -> str:
    if goal_state.state == "verified":
        return "verified"
    if goal_state.state == "blocked":
        return "blocked"
    if unmet_dependencies:
        return "waiting"
    if goal_state.state in {"ready", "released"}:
        return "ready"
    return goal_state.state


def _goal_package(
    *,
    loop_id: str,
    node: LoopNode,
    goal_contract: dict[str, Any],
    goal_state: GoalState,
    command: str,
) -> dict[str, Any]:
    boundaries = goal_contract.get("boundaries")
    evidence = goal_contract.get("evidence")
    read_first = []
    allowed_paths = []
    evidence_plan = node.evidence_plan
    if isinstance(boundaries, dict):
        read_first = _list_or_empty(boundaries.get("read_first"))
        allowed_paths = _list_or_empty(boundaries.get("allowed_paths"))
    if evidence_plan is None and isinstance(evidence, dict):
        evidence_plan = _non_empty_string(evidence.get("evidence_plan"))

    return {
        "ok": True,
        "command": command,
        "loop_id": loop_id,
        "node_id": node.node_id,
        "goal_id": node.goal_id,
        "goal_path": node.goal_path.as_posix(),
        "beads_issue_id": node.beads_issue_id,
        "lease": goal_state.lease,
        "read_first": read_first,
        "evidence_plan": evidence_plan,
        "allowed_paths": allowed_paths,
        "commands": _goal_commands(node.goal_path),
    }


def _goal_commands(goal_path: Path) -> dict[str, str]:
    path = goal_path.as_posix()
    return {
        "start": f"dp goal start {path} --agent codex --json",
        "heartbeat": f"dp goal heartbeat {path} --json",
        "complete": f"dp goal complete {path} --evidence <run.json> --json",
        "verify": f"dp goal verify {path} --evidence <run.json> --json",
        "block": f"dp goal block {path} --reason <reason> --write-artifact --json",
        "release": f"dp goal release {path} --reason <reason> --json",
    }


def _read_goal_contract(goal_path: Path) -> dict[str, Any]:
    payload = json.loads(goal_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Valid GoalContract unexpectedly loaded as non-object.")
    return payload


def _lint_failure_payload(command: str, result: LoopLintResult) -> LoopCommandResult:
    return LoopCommandResult(
        payload={
            "ok": False,
            "command": command,
            "lint": result.report.to_dict(),
        },
        exit_code=result.exit_code,
    )


def _usage_error(command: str, code: str, path: str, message: str) -> LoopCommandResult:
    return LoopCommandResult(
        payload={
            "ok": False,
            "command": command,
            "error": {
                "code": code,
                "path": path,
                "message": message,
            },
        },
        exit_code=2,
    )


def _input_error(
    *,
    code: str,
    path: str,
    message: str,
    loop_id: str | None = None,
) -> LoopLintResult:
    return LoopLintResult(
        report=LoopLintReport(
            valid=False,
            loop_id=loop_id,
            errors=(_finding(code, path, message),),
        ),
        exit_code=2,
    )


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    values: list[str] = []
    for item in value:
        text = _non_empty_string(item)
        if text is None:
            return None
        values.append(text)
    return values


def _list_or_empty(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


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


def _finding(code: str, path: str, message: str) -> LoopLintFinding:
    return LoopLintFinding(code=code, path=path, message=message)
