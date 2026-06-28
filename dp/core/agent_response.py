from __future__ import annotations

from typing import Any

RESPONSE_SCHEMA_VERSION = "dp.response.v1"
DETAIL_MODES = ("brief", "normal", "full")


def cost(
    *,
    latency: str = "low",
    tokens: str = "low",
    executes_commands: bool = False,
    network: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "latency": latency,
        "tokens": tokens,
        "executes_commands": executes_commands,
    }
    if network:
        payload["network"] = True
    return payload


def affordances(
    *,
    phase: str,
    mutability: str,
    idempotent: bool,
    safety: str,
    freshness: str = "current",
    cost_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "mutability": mutability,
        "idempotent": idempotent,
        "safety": safety,
        "freshness": freshness,
        "cost": cost_payload or cost(),
    }


def next_action(
    action_id: str,
    command: str,
    why: str,
    *,
    label: str | None = None,
) -> dict[str, str]:
    payload = {
        "id": action_id,
        "command": command,
        "why": why,
    }
    if label is not None:
        payload["label"] = label
    return payload


def hint(
    code: str,
    message: str,
    *,
    severity: str = "info",
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "explain_command": f"dp explain {code} --json",
    }


def artifact(kind: str, path: str, *, artifact_id: str | None = None) -> dict[str, str]:
    payload = {
        "kind": kind,
        "path": path,
    }
    if artifact_id is not None:
        payload["id"] = artifact_id
    return payload


def expansion(expansion_id: str, command: str, *, why: str | None = None) -> dict[str, str]:
    payload = {
        "id": expansion_id,
        "command": command,
    }
    if why is not None:
        payload["why"] = why
    return payload


def agent_response(
    *,
    command: str,
    status: str,
    exit_code: int,
    summary: str,
    affordance_payload: dict[str, Any],
    result: dict[str, Any] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
    hints: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    expansions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "command": command,
        "status": status,
        "exit_code": exit_code,
        "summary": summary,
        "result": result or {},
        "affordances": affordance_payload,
        "next_actions": next_actions or [],
        "hints": hints or [],
        "artifacts": artifacts or [],
        "expansions": expansions or [],
    }


def response_status(ok: bool | None, exit_code: int, *, blocked: bool = False) -> str:
    if blocked:
        return "blocked"
    if ok is True and exit_code == 0:
        return "ok"
    if exit_code == 2:
        return "invalid"
    if exit_code == 1:
        return "incomplete"
    return "error"


def validate_detail(detail: str) -> str:
    if detail not in DETAIL_MODES:
        raise ValueError(f"detail must be one of: {', '.join(DETAIL_MODES)}")
    return detail


def envelope_legacy_payload(
    *,
    command: str,
    payload: dict[str, Any],
    exit_code: int,
    detail: str,
    phase: str,
    mutability: str,
    idempotent: bool,
    safety: str,
    summary: str,
    cost_payload: dict[str, Any] | None = None,
    normal_result: dict[str, Any] | None = None,
    brief_result: dict[str, Any] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
    hints: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    expansions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_detail(detail)
    if detail == "full":
        result = {"payload": payload}
    elif detail == "normal":
        result = normal_result if normal_result is not None else compact_result(payload)
    else:
        result = brief_result if brief_result is not None else {}

    return agent_response(
        command=command,
        status=response_status(_payload_ok(payload), exit_code),
        exit_code=exit_code,
        summary=summary,
        result=result,
        affordance_payload=affordances(
            phase=phase,
            mutability=mutability,
            idempotent=idempotent,
            safety=safety,
            cost_payload=cost_payload,
        ),
        next_actions=next_actions,
        hints=hints,
        artifacts=artifacts,
        expansions=expansions,
    )


def compact_result(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ok",
        "command",
        "goal_id",
        "goal_path",
        "state",
        "loop_id",
        "node_id",
        "campaign_id",
        "derived_status",
        "stop_reason",
        "evidence_id",
        "evidence_status",
        "summary",
        "error",
        "artifact",
    )
    return {key: payload[key] for key in keys if key in payload}


def _payload_ok(payload: dict[str, Any]) -> bool | None:
    value = payload.get("ok")
    return value if isinstance(value, bool) else None
