from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.goal_lint import lint_goal_file

# @trace SPEC-80.03

@dataclass(frozen=True)
class GoalEmitResult:
    payload: dict[str, Any]
    exit_code: int


def emit_goal_prompt(goal_path: Path, *, output_format: str) -> GoalEmitResult:
    if output_format != "codex":
        return GoalEmitResult(
            payload={
                "ok": False,
                "error": {
                    "code": "unsupported_format",
                    "message": "Only codex format is supported.",
                },
            },
            exit_code=2,
        )

    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return GoalEmitResult(
            payload={
                "ok": False,
                "format": output_format,
                "lint": lint_result.report.to_dict(),
            },
            exit_code=lint_result.exit_code,
        )

    import json

    contract = json.loads(goal_path.read_text(encoding="utf-8"))
    goal_id = str(contract["id"])
    objective = str(contract["objective"])
    evidence = contract.get("evidence", {})
    boundaries = contract.get("boundaries", {})
    iteration_policy = contract.get("iteration_policy", {})
    terminal_states = contract.get("terminal_states", {})

    commands = {
        "start": f"dp goal start {goal_path.as_posix()} --agent codex --json",
        "heartbeat": f"dp goal heartbeat {goal_path.as_posix()} --json",
        "complete": f"dp goal complete {goal_path.as_posix()} --evidence <run.json> --json",
        "block": f"dp goal block {goal_path.as_posix()} --reason <reason> --json",
        "release": f"dp goal release {goal_path.as_posix()} --reason <reason> --json",
    }

    codex_goal = _render_codex_goal(
        objective=objective,
        evidence=evidence,
        boundaries=boundaries,
        iteration_policy=iteration_policy,
        terminal_states=terminal_states,
        commands=commands,
    )
    payload: dict[str, Any] = {
        "ok": True,
        "format": "codex",
        "goal_id": goal_id,
        "codex_goal": codex_goal,
        "read_first": boundaries.get("read_first", []),
        "allowed_paths": boundaries.get("allowed_paths", []),
        "evidence": evidence,
        "commands": commands,
    }
    return GoalEmitResult(payload=payload, exit_code=0)


def _render_codex_goal(
    *,
    objective: str,
    evidence: Any,
    boundaries: Any,
    iteration_policy: Any,
    terminal_states: Any,
    commands: dict[str, str],
) -> str:
    evidence_text = _evidence_text(evidence)
    read_first = _list_text(
        boundaries.get("read_first", []) if isinstance(boundaries, dict) else []
    )
    allowed_paths = _list_text(
        boundaries.get("allowed_paths", []) if isinstance(boundaries, dict) else []
    )
    allowed_commands = _list_text(
        boundaries.get("allowed_commands", []) if isinstance(boundaries, dict) else []
    )
    policy_mode = "smallest_relevant_check_first"
    if isinstance(iteration_policy, dict) and isinstance(iteration_policy.get("mode"), str):
        policy_mode = iteration_policy["mode"]
    blocked = "Required context, fixture, command, validator, or decision is missing."
    if isinstance(terminal_states, dict) and isinstance(terminal_states.get("blocked"), str):
        blocked = terminal_states["blocked"]

    return (
        f"/goal {objective} Verify with {evidence_text}. "
        f"Start the goal through dp using `{commands['start']}`. "
        f"Read first: {read_first}. Stay inside allowed paths: {allowed_paths}. "
        f"Use allowed commands as evidence cues: {allowed_commands}. "
        f"Between iterations, follow `{policy_mode}`: run the smallest relevant check first, "
        "repair failures before broadening scope, and keep progress in dp. "
        f"If blocked, budget-exhausted, or no safe path remains, use `{commands['block']}`; "
        f"blocked means: {blocked}. Release with `{commands['release']}` on context reset. "
        "Never claim completion from narration; record evidence with "
        f"`{commands['complete']}` only after evidence exists."
    )


def _evidence_text(evidence: Any) -> str:
    if not isinstance(evidence, dict):
        return "the goal evidence contract"
    parts: list[str] = []
    if isinstance(evidence.get("evidence_plan"), str):
        parts.append(str(evidence["evidence_plan"]))
    if isinstance(evidence.get("verification_commands"), list):
        parts.extend(str(command) for command in evidence["verification_commands"])
    if isinstance(evidence.get("trace_ids"), list):
        parts.append("trace IDs " + ", ".join(str(item) for item in evidence["trace_ids"]))
    return "; ".join(parts) if parts else "the goal evidence contract"


def _list_text(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none declared"
    return ", ".join(str(item) for item in value)
