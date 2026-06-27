from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.goal_emit import emit_goal_prompt
from dp.core.goal_state import (
    DEFAULT_GOAL_EVENT_LOG,
    GoalCommandResult,
    claim_goal,
    start_goal,
)

# @trace SPEC-80.20
SUPPORTED_AGENT_LAUNCH_DRIVERS = frozenset({"codex"})


@dataclass(frozen=True)
class AgentLaunchResult:
    payload: dict[str, Any]
    exit_code: int


def launch_agent_goal(
    goal_path: Path,
    *,
    driver: str,
    supervised: bool,
    agent: str,
    lease: str,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> AgentLaunchResult:
    if not supervised:
        return _usage_error(
            driver=driver,
            supervised=supervised,
            agent=agent,
            code="supervised_required",
            path="$.supervised",
            message="dp agent launch requires --supervised in this slice.",
        )
    if driver not in SUPPORTED_AGENT_LAUNCH_DRIVERS:
        return _usage_error(
            driver=driver,
            supervised=supervised,
            agent=agent,
            code="unsupported_driver",
            path="$.driver",
            message="Only the codex supervised driver is supported.",
        )
    if not agent.strip():
        return _usage_error(
            driver=driver,
            supervised=supervised,
            agent=agent,
            code="agent_required",
            path="$.agent",
            message="Agent must be non-empty.",
        )

    emit_result = emit_goal_prompt(goal_path, output_format="codex")
    base_payload = _base_payload(driver=driver, supervised=supervised, agent=agent)
    if emit_result.exit_code != 0:
        return AgentLaunchResult(
            payload={
                **base_payload,
                "ok": False,
                "goal_id": _goal_id_from_payload(emit_result.payload),
                "goal_path": goal_path.as_posix(),
                "emit": emit_result.payload,
                "error": {
                    "code": "goal_emit_failed",
                    "path": "$.goal",
                    "message": "Goal prompt could not be emitted.",
                },
            },
            exit_code=emit_result.exit_code,
        )

    claim_result = claim_goal(goal_path, agent=agent, lease=lease, event_log=event_log)
    if claim_result.exit_code != 0:
        return _lifecycle_failure(
            base_payload=base_payload,
            goal_path=goal_path,
            emit_payload=emit_result.payload,
            result=claim_result,
            code="goal_claim_failed",
            path="$.claim",
            message="Goal could not be claimed.",
        )

    start_result = start_goal(goal_path, agent=agent, event_log=event_log)
    if start_result.exit_code != 0:
        return _lifecycle_failure(
            base_payload=base_payload,
            goal_path=goal_path,
            emit_payload=emit_result.payload,
            result=start_result,
            code="goal_start_failed",
            path="$.start",
            message="Goal could not be started.",
            claim_payload=claim_result.payload,
        )

    return AgentLaunchResult(
        payload={
            **base_payload,
            "ok": True,
            "goal_id": emit_result.payload.get("goal_id"),
            "goal_path": goal_path.as_posix(),
            "codex_goal": emit_result.payload.get("codex_goal"),
            "read_first": emit_result.payload.get("read_first", []),
            "allowed_paths": emit_result.payload.get("allowed_paths", []),
            "evidence": emit_result.payload.get("evidence", {}),
            "commands": emit_result.payload.get("commands", {}),
            "emit": emit_result.payload,
            "claim": claim_result.payload,
            "start": start_result.payload,
            "message": (
                "Supervised agent launch package prepared; no process was spawned."
            ),
        },
        exit_code=0,
    )


def _lifecycle_failure(
    *,
    base_payload: dict[str, Any],
    goal_path: Path,
    emit_payload: dict[str, Any],
    result: GoalCommandResult,
    code: str,
    path: str,
    message: str,
    claim_payload: dict[str, Any] | None = None,
) -> AgentLaunchResult:
    payload: dict[str, Any] = {
        **base_payload,
        "ok": False,
        "goal_id": emit_payload.get("goal_id"),
        "goal_path": goal_path.as_posix(),
        "emit": emit_payload,
        "error": {
            "code": code,
            "path": path,
            "message": message,
        },
    }
    if claim_payload is not None:
        payload["claim"] = claim_payload
    payload[path.removeprefix("$.")] = result.payload
    return AgentLaunchResult(payload=payload, exit_code=result.exit_code)


def _base_payload(*, driver: str, supervised: bool, agent: str) -> dict[str, Any]:
    return {
        "command": "agent.launch",
        "mode": "supervised_goal_launch",
        "driver": driver,
        "agent": agent,
        "supervised": supervised,
        "autonomous": False,
        "launched": False,
        "stop_conditions": _stop_conditions(),
    }


def _usage_error(
    *,
    driver: str,
    supervised: bool,
    agent: str,
    code: str,
    path: str,
    message: str,
) -> AgentLaunchResult:
    return AgentLaunchResult(
        payload={
            **_base_payload(driver=driver, supervised=supervised, agent=agent),
            "ok": False,
            "goal_id": None,
            "goal_path": None,
            "error": {
                "code": code,
                "path": path,
                "message": message,
            },
        },
        exit_code=2,
    )


def _goal_id_from_payload(payload: dict[str, Any]) -> str | None:
    goal_id = payload.get("goal_id")
    if isinstance(goal_id, str):
        return goal_id
    lint = payload.get("lint")
    if isinstance(lint, dict):
        lint_goal_id = lint.get("goal_id")
        if isinstance(lint_goal_id, str):
            return lint_goal_id
    return None


def _stop_conditions() -> list[str]:
    return [
        "This command only claims and starts one goal; it never spawns Codex.",
        "Use the emitted codex_goal text in the calling agent session.",
        "Run evidence and verification through the emitted dp commands.",
        "Block or release through dp when a decision, spec, validator, or safe path is missing.",
        "Never claim completion from agent narration; completion requires recorded evidence.",
    ]
