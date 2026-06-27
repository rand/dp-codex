from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from dp.core.adr import create_adr
from dp.providers.beads import BdUnavailableError, BeadsNotInitializedError, run_bd

# @trace SPEC-80.14

SUPPORTED_ROUTE_ACTIONS = frozenset(
    {
        "create_spec_stub",
        "create_adr_stub",
        "create_evidence_stub",
    }
)


@dataclass(frozen=True)
class BlockerRoutingResult:
    routing: dict[str, Any]
    error: dict[str, str] | None
    exit_code: int


def route_blocker_artifact(
    *,
    goal_path: Path,
    goal_contract: dict[str, Any],
    reason: str,
) -> BlockerRoutingResult:
    goal_id = _text(goal_contract.get("id")) or "<unknown>"
    routes = goal_contract.get("blocked_routes")
    if not isinstance(routes, dict) or not isinstance(routes.get(reason), dict):
        error = {
            "code": "missing_blocked_route",
            "path": f"$.blocked_routes.{reason}",
            "message": f"GoalContract does not define a blocker route for {reason}.",
        }
        return BlockerRoutingResult(
            routing={
                "ok": False,
                "reason": reason,
                "action": None,
                "artifact": None,
                "beads": _beads_not_requested(),
                "error": error,
            },
            error=error,
            exit_code=1,
        )

    route = routes[reason]
    action = _text(route.get("action"))
    if action not in SUPPORTED_ROUTE_ACTIONS:
        error = {
            "code": "unsupported_blocked_route_action",
            "path": f"$.blocked_routes.{reason}.action",
            "message": f"Blocked route action is not implemented: {action or '<missing>'}.",
        }
        return BlockerRoutingResult(
            routing={
                "ok": False,
                "reason": reason,
                "action": action,
                "artifact": None,
                "beads": _beads_not_requested(),
                "error": error,
            },
            error=error,
            exit_code=1,
        )

    try:
        artifact_result = _write_route_artifact(
            action=action,
            goal_path=goal_path,
            goal_contract=goal_contract,
            reason=reason,
        )
    except OSError as exc:
        artifact_result = {
            "ok": False,
            "error": {
                "code": "artifact_write_failed",
                "path": f"$.blocked_routes.{reason}",
                "message": str(exc),
            },
        }
    routing: dict[str, Any] = {
        "ok": artifact_result["ok"],
        "reason": reason,
        "action": action,
        "artifact": artifact_result.get("artifact"),
        "beads": _beads_not_requested(),
    }
    if artifact_result["ok"] is not True:
        error = artifact_result["error"]
        routing["error"] = error
        return BlockerRoutingResult(routing=routing, error=error, exit_code=2)

    if bool(route.get("also_create_beads_issue")):
        beads = _create_beads_followup(
            goal_id=goal_id,
            goal_title=_text(goal_contract.get("title")) or goal_id,
            goal_path=goal_path,
            reason=reason,
            action=action,
            artifact=routing["artifact"],
        )
        routing["beads"] = beads
        if beads.get("ok") is not True:
            error = beads["error"]
            routing["ok"] = False
            routing["error"] = error
            return BlockerRoutingResult(routing=routing, error=error, exit_code=1)

    return BlockerRoutingResult(routing=routing, error=None, exit_code=0)


def _write_route_artifact(
    *,
    action: str,
    goal_path: Path,
    goal_contract: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if action == "create_spec_stub":
        path = Path("docs/specs") / f"BLOCKER-{_slug(goal_contract['id'])}-{_slug(reason)}.md"
        content = _render_spec_stub(goal_contract=goal_contract, goal_path=goal_path, reason=reason)
        return _write_deterministic_artifact(kind="spec", path=path, content=content)

    if action == "create_evidence_stub":
        path = (
            Path("docs/evidence")
            / f"EVIDENCE-BLOCKER-{_slug(goal_contract['id'])}-{_slug(reason)}.json"
        )
        content = _render_evidence_stub(
            goal_contract=goal_contract,
            goal_path=goal_path,
            reason=reason,
        )
        return _write_deterministic_artifact(kind="evidence_plan", path=path, content=content)

    if action == "create_adr_stub":
        title = f"Resolve {goal_contract['id']} blocker: {reason.replace('_', ' ')}"
        record = create_adr(title, Path("docs/adr"), status="proposal")
        adr_path = Path(record.path)
        return {
            "ok": True,
            "artifact": {
                "kind": "adr",
                "path": adr_path.as_posix(),
                "reused": False,
            },
        }

    raise AssertionError(f"Unhandled supported action: {action}")


def _write_deterministic_artifact(*, kind: str, path: Path, content: str) -> dict[str, Any]:
    if not _is_sane_relative_path(path):
        return {
            "ok": False,
            "error": {
                "code": "invalid_artifact_path",
                "path": "$.blocked_routes",
                "message": f"Artifact path is not a sane relative path: {path.as_posix()}",
            },
        }
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return {
                "ok": True,
                "artifact": {
                    "kind": kind,
                    "path": path.as_posix(),
                    "reused": True,
                },
            }
        return {
            "ok": False,
            "error": {
                "code": "artifact_exists",
                "path": path.as_posix(),
                "message": (
                    "Route artifact already exists with different content; refusing to overwrite."
                ),
            },
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "artifact": {
            "kind": kind,
            "path": path.as_posix(),
            "reused": False,
        },
    }


def _render_spec_stub(
    *,
    goal_contract: dict[str, Any],
    goal_path: Path,
    reason: str,
) -> str:
    goal_id = str(goal_contract["id"])
    title = _text(goal_contract.get("title")) or goal_id
    today = date.today().isoformat()
    source = goal_contract.get("source")
    source_text = "not declared"
    if isinstance(source, dict):
        source_id = _text(source.get("id"))
        source_path = _text(source.get("path"))
        if source_id and source_path:
            source_text = f"{source_id} ({source_path})"
        elif source_id:
            source_text = source_id
        elif source_path:
            source_text = source_path

    return (
        f"# Blocker Specification for {goal_id}\n\n"
        "Status: draft\n"
        f"Created: {today}\n"
        f"Source Goal: {goal_id}\n"
        f"Source Goal Path: {goal_path.as_posix()}\n"
        f"Blocker Reason: {reason}\n"
        "Trace: [SPEC-80.14]\n\n"
        "## Context\n\n"
        f"`{goal_id}` blocked while pursuing `{title}`.\n\n"
        f"Source context: {source_text}.\n\n"
        "## Missing Specification\n\n"
        "Describe the requirement, fixture, acceptance criterion, or process rule that must exist "
        "before the goal can proceed safely.\n\n"
        "## Acceptance Criteria\n\n"
        "1. The missing specification is explicit enough for a GoalContract or EvidencePlan "
        "update.\n"
        "2. The resulting artifact is linked from the blocked goal or campaign.\n"
        "3. Deterministic gates can validate the updated work.\n"
    )


def _render_evidence_stub(
    *,
    goal_contract: dict[str, Any],
    goal_path: Path,
    reason: str,
) -> str:
    goal_id = str(goal_contract["id"])
    evidence_id = f"EVIDENCE-BLOCKER-{_evidence_id_suffix(goal_id)}-{_slug(reason)}"
    payload = {
        "schema_version": "0.1",
        "id": evidence_id,
        "goal_id": goal_id,
        "checks": [
            {
                "id": "goal-contract-lint",
                "kind": "registered_command",
                "argv": ["dp", "goal", "lint", goal_path.as_posix(), "--json"],
                "timeout_seconds": 30,
                "success_exit_codes": [0],
                "assertions": [
                    {"type": "stdout_json"},
                    {"type": "json_path_equals", "path": "$.valid", "value": True},
                ],
                "mutation_policy": "read_only",
            }
        ],
        "blocker": {
            "reason": reason,
            "source_goal_path": goal_path.as_posix(),
            "created_by": "dp goal block --write-artifact",
            "trace": "SPEC-80.14",
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _create_beads_followup(
    *,
    goal_id: str,
    goal_title: str,
    goal_path: Path,
    reason: str,
    action: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    command = [
        "create",
        f"Resolve blocker for {goal_id}: {reason.replace('_', ' ')}",
        "--type",
        "task",
        "--priority",
        "P2",
        "--description",
        (
            f"Goal {goal_id} blocked with reason {reason}. "
            f"Goal path: {goal_path.as_posix()}. "
            f"Route action: {action}. Artifact: {artifact.get('path')}. "
            f"Goal title: {goal_title}."
        ),
        "--acceptance",
        "The blocker artifact is resolved and the original goal can be retried or updated.",
        "--labels",
        "campaign-control,blocker,goal-contracts",
        "--json",
    ]

    try:
        result = run_bd(command)
    except (BdUnavailableError, BeadsNotInitializedError) as exc:
        return {
            "requested": True,
            "ok": False,
            "issue_id": None,
            "command": command,
            "error": {"code": "beads_unavailable", "message": str(exc)},
        }
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "bd create failed"
        return {
            "requested": True,
            "ok": False,
            "issue_id": None,
            "command": command,
            "error": {"code": "beads_create_failed", "message": message},
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "requested": True,
            "ok": False,
            "issue_id": None,
            "command": command,
            "error": {
                "code": "beads_create_failed",
                "message": f"bd create did not emit valid JSON: {exc}",
            },
        }

    issue_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(issue_id, str) or not issue_id:
        return {
            "requested": True,
            "ok": False,
            "issue_id": None,
            "command": command,
            "error": {
                "code": "beads_create_failed",
                "message": "bd create JSON did not include an id.",
            },
        }

    return {
        "requested": True,
        "ok": True,
        "issue_id": issue_id,
        "command": command,
    }


def _beads_not_requested() -> dict[str, Any]:
    return {
        "requested": False,
        "ok": None,
        "issue_id": None,
    }


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _slug(value: Any) -> str:
    text = str(value).replace("_", "-")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return slug or "artifact"


def _evidence_id_suffix(goal_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "-", goal_id).strip("-")
    return suffix or "GOAL"


def _is_sane_relative_path(path: Path) -> bool:
    return (
        bool(path.as_posix())
        and not path.is_absolute()
        and not path.as_posix().startswith(("-", "~"))
        and ".." not in path.parts
    )
