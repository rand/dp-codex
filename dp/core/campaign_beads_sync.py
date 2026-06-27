from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.campaign_manifest import CampaignCommandResult, lint_campaign_file
from dp.core.goal_state import DEFAULT_GOAL_EVENT_LOG
from dp.core.loop_ledger import loop_status
from dp.providers.beads import BdUnavailableError, BeadsNotInitializedError, run_bd

# @trace SPEC-80.18


@dataclass(frozen=True)
class CampaignBeadsSyncResult:
    payload: dict[str, Any]
    exit_code: int


def sync_campaign_beads(
    campaign_path: Path,
    *,
    write: bool,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> CampaignBeadsSyncResult:
    lint_result = lint_campaign_file(campaign_path)
    if lint_result.exit_code != 0:
        return CampaignBeadsSyncResult(
            payload={
                "ok": False,
                "command": "campaign.sync-beads",
                "campaign_id": lint_result.report.campaign_id,
                "write": write,
                "lint": lint_result.report.to_dict(),
            },
            exit_code=lint_result.exit_code,
        )

    campaign = _read_json_object(campaign_path)
    campaign_id = str(campaign["id"])
    loop_path_result = _current_loop_path(campaign_path, campaign)
    if loop_path_result.exit_code != 0:
        return CampaignBeadsSyncResult(
            payload={
                "ok": False,
                "command": "campaign.sync-beads",
                "campaign_id": campaign_id,
                "write": write,
                "error": loop_path_result.payload["error"],
            },
            exit_code=loop_path_result.exit_code,
        )

    loop_path = Path(loop_path_result.payload["loop_path"])
    status_result = loop_status(loop_path, event_log=event_log)
    if status_result.exit_code != 0:
        return CampaignBeadsSyncResult(
            payload={
                "ok": False,
                "command": "campaign.sync-beads",
                "campaign_id": campaign_id,
                "write": write,
                "loop": status_result.payload,
            },
            exit_code=status_result.exit_code,
        )

    operations = _plan_operations(status_result.payload)
    applied_operations = _apply_operations(operations, write=write)
    summary = _summary(applied_operations)
    ok = summary["failed"] == 0
    return CampaignBeadsSyncResult(
        payload={
            "ok": ok,
            "command": "campaign.sync-beads",
            "campaign_id": campaign_id,
            "loop_id": status_result.payload.get("loop_id"),
            "write": write,
            "operations": applied_operations,
            "summary": summary,
        },
        exit_code=0 if ok else 1,
    )


def _current_loop_path(campaign_path: Path, campaign: dict[str, Any]) -> CampaignCommandResult:
    state = campaign.get("state")
    artifacts = campaign.get("artifacts")
    current_loop = state.get("current_loop") if isinstance(state, dict) else None
    loop_paths = artifacts.get("loops") if isinstance(artifacts, dict) else None
    if not isinstance(current_loop, str) or not isinstance(loop_paths, list):
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.sync-beads",
                "error": {
                    "code": "current_loop_unresolved",
                    "path": "$.state.current_loop",
                    "message": "Campaign current loop could not be resolved.",
                },
            },
            exit_code=1,
        )

    for item in loop_paths:
        if not isinstance(item, str):
            continue
        loop_path = Path(item)
        try:
            loop_payload = json.loads(loop_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if isinstance(loop_payload, dict) and loop_payload.get("id") == current_loop:
            return CampaignCommandResult(
                payload={
                    "ok": True,
                    "command": "campaign.sync-beads",
                    "loop_path": loop_path,
                },
                exit_code=0,
            )

    return CampaignCommandResult(
        payload={
            "ok": False,
            "command": "campaign.sync-beads",
            "error": {
                "code": "current_loop_unresolved",
                "path": "$.state.current_loop",
                "message": "Campaign current loop does not match a readable declared loop.",
            },
        },
        exit_code=1,
    )


def _plan_operations(loop_payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node for node in loop_payload.get("nodes", []) if isinstance(node, dict)]
    by_node_id = {
        str(node["node_id"]): node
        for node in nodes
        if isinstance(node.get("node_id"), str)
    }
    operations: list[dict[str, Any]] = []

    for node in nodes:
        issue_id = _non_empty_string(node.get("beads_issue_id"))
        if issue_id is None:
            continue
        for dependency_node_id in _string_list(node.get("depends_on")):
            dependency_node = by_node_id.get(dependency_node_id)
            if dependency_node is None:
                continue
            depends_on_id = _non_empty_string(dependency_node.get("beads_issue_id"))
            if depends_on_id is None:
                continue
            operations.append(_dependency_operation(node, dependency_node, issue_id, depends_on_id))
        blocker_issue_id = _blocked_followup_issue_id(node)
        if blocker_issue_id is not None:
            operations.append(
                _blocker_dependency_operation(
                    node=node,
                    issue_id=issue_id,
                    blocker_issue_id=blocker_issue_id,
                )
            )

    for node in nodes:
        issue_id = _non_empty_string(node.get("beads_issue_id"))
        if issue_id is None:
            continue
        operation = _lifecycle_operation(node, issue_id)
        if operation is not None:
            operations.append(operation)

    return operations


def _dependency_operation(
    node: dict[str, Any],
    dependency_node: dict[str, Any],
    issue_id: str,
    depends_on_id: str,
) -> dict[str, Any]:
    return {
        "kind": "dependency",
        "action": "add",
        "issue_id": issue_id,
        "depends_on_id": depends_on_id,
        "dependency_type": "blocks",
        "node_id": str(node["node_id"]),
        "depends_on_node_id": str(dependency_node["node_id"]),
        "status": "planned",
        "command": [
            "dep",
            "add",
            issue_id,
            depends_on_id,
            "--type",
            "blocks",
            "--json",
        ],
    }


def _blocker_dependency_operation(
    *,
    node: dict[str, Any],
    issue_id: str,
    blocker_issue_id: str,
) -> dict[str, Any]:
    return {
        "kind": "dependency",
        "action": "add",
        "issue_id": issue_id,
        "depends_on_id": blocker_issue_id,
        "dependency_type": "blocks",
        "node_id": str(node["node_id"]),
        "depends_on_node_id": "blocked_route",
        "status": "planned",
        "command": [
            "dep",
            "add",
            issue_id,
            blocker_issue_id,
            "--type",
            "blocks",
            "--json",
        ],
    }


def _lifecycle_operation(node: dict[str, Any], issue_id: str) -> dict[str, Any] | None:
    goal_state = _non_empty_string(node.get("goal_state"))
    goal_id = _non_empty_string(node.get("goal_id")) or "<unknown>"
    last_event = node.get("last_event")
    event = last_event if isinstance(last_event, dict) else {}

    if goal_state in {"claimed", "started", "pursuing"}:
        note = f"dp campaign sync-beads: goal {goal_id} is {goal_state}."
        return {
            "kind": "lifecycle",
            "action": "update",
            "issue_id": issue_id,
            "goal_id": goal_id,
            "goal_state": goal_state,
            "status": "planned",
            "command": [
                "update",
                issue_id,
                "--status",
                "in_progress",
                "--append-notes",
                note,
                "--json",
            ],
        }

    if goal_state == "blocked":
        reason = _non_empty_string(event.get("reason")) or "unknown"
        note = f"dp campaign sync-beads: goal {goal_id} blocked with reason {reason}."
        operation = {
            "kind": "lifecycle",
            "action": "update",
            "issue_id": issue_id,
            "goal_id": goal_id,
            "goal_state": goal_state,
            "block_reason": reason,
            "status": "planned",
            "command": [
                "update",
                issue_id,
                "--status",
                "blocked",
                "--append-notes",
                note,
                "--json",
            ],
        }
        if isinstance(event.get("routing"), dict):
            operation["routing"] = event["routing"]
        return operation

    if goal_state == "released":
        reason = _non_empty_string(event.get("reason")) or "unspecified"
        note = f"dp campaign sync-beads: goal {goal_id} released: {reason}."
        return {
            "kind": "lifecycle",
            "action": "update",
            "issue_id": issue_id,
            "goal_id": goal_id,
            "goal_state": goal_state,
            "release_reason": reason,
            "status": "planned",
            "command": [
                "update",
                issue_id,
                "--status",
                "open",
                "--append-notes",
                note,
                "--json",
            ],
        }

    if goal_state == "verified":
        evidence = _non_empty_string(event.get("evidence"))
        if evidence is None:
            reason = f"dp campaign sync-beads: goal {goal_id} verified."
        else:
            reason = f"dp campaign sync-beads: goal {goal_id} verified with evidence {evidence}."
        return {
            "kind": "lifecycle",
            "action": "close",
            "issue_id": issue_id,
            "goal_id": goal_id,
            "goal_state": goal_state,
            "evidence": evidence,
            "status": "planned",
            "command": [
                "close",
                issue_id,
                "--reason",
                reason,
                "--json",
            ],
        }

    return None


def _blocked_followup_issue_id(node: dict[str, Any]) -> str | None:
    if _non_empty_string(node.get("goal_state")) != "blocked":
        return None
    last_event = node.get("last_event")
    if not isinstance(last_event, dict):
        return None
    routing = last_event.get("routing")
    if not isinstance(routing, dict):
        return None
    beads = routing.get("beads")
    if not isinstance(beads, dict) or beads.get("ok") is not True:
        return None
    return _non_empty_string(beads.get("issue_id"))


def _apply_operations(operations: list[dict[str, Any]], *, write: bool) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    existing_dependency_cache: dict[str, set[tuple[str, str, str]]] = {}
    for operation in operations:
        prepared = dict(operation)
        if operation["kind"] == "dependency":
            issue_id = str(operation["issue_id"])
            existing = existing_dependency_cache.get(issue_id)
            if existing is None:
                result = _read_existing_dependencies(issue_id)
                if isinstance(result, dict):
                    prepared["status"] = "failed"
                    prepared["error"] = result
                    applied.append(prepared)
                    break
                existing = result
                existing_dependency_cache[issue_id] = existing
            edge = (
                str(operation["issue_id"]),
                str(operation["depends_on_id"]),
                str(operation["dependency_type"]),
            )
            if edge in existing:
                prepared["status"] = "skipped"
                applied.append(prepared)
                continue

        if not write:
            prepared["status"] = "planned"
            applied.append(prepared)
            continue

        operation_error = _run_operation(operation)
        if operation_error is not None:
            prepared["status"] = "failed"
            prepared["error"] = operation_error
            applied.append(prepared)
            break
        prepared["status"] = "applied"
        applied.append(prepared)
    return applied


def _read_existing_dependencies(issue_id: str) -> set[tuple[str, str, str]] | dict[str, str]:
    command = ["dep", "list", issue_id, "--json"]
    try:
        result = run_bd(command)
    except (BdUnavailableError, BeadsNotInitializedError) as exc:
        return {"code": "beads_unavailable", "message": str(exc)}
    if result.returncode != 0:
        return {
            "code": "beads_command_failed",
            "message": _command_message(result, "bd dep list failed"),
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "code": "beads_invalid_json",
            "message": f"bd dep list did not emit valid JSON: {exc}",
        }
    if not isinstance(payload, list):
        return {
            "code": "beads_invalid_json",
            "message": "bd dep list JSON must be an array.",
        }
    edges: set[tuple[str, str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        issue = _non_empty_string(item.get("issue_id")) or _non_empty_string(item.get("from"))
        depends_on = _non_empty_string(item.get("depends_on_id")) or _non_empty_string(
            item.get("to")
        )
        dependency_type = _non_empty_string(item.get("type")) or "blocks"
        if issue is not None and depends_on is not None:
            edges.add((issue, depends_on, dependency_type))
    return edges


def _run_operation(operation: dict[str, Any]) -> dict[str, str] | None:
    try:
        result = run_bd(operation["command"])
    except (BdUnavailableError, BeadsNotInitializedError) as exc:
        return {"code": "beads_unavailable", "message": str(exc)}
    if result.returncode != 0:
        return {
            "code": "beads_command_failed",
            "message": _command_message(result, "bd command failed"),
        }
    return None


def _summary(operations: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "planned": sum(1 for operation in operations if operation.get("status") == "planned"),
        "applied": sum(1 for operation in operations if operation.get("status") == "applied"),
        "skipped": sum(1 for operation in operations if operation.get("status") == "skipped"),
        "failed": sum(1 for operation in operations if operation.get("status") == "failed"),
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Valid CampaignManifest unexpectedly loaded as non-object.")
    return payload


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _command_message(result: Any, fallback: str) -> str:
    return result.stderr.strip() or result.stdout.strip() or fallback
