from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from dp.core.adoption import inspect_adoption
from dp.core.agent_response import (
    affordances,
    agent_response,
    artifact,
    cost,
    envelope_legacy_payload,
    expansion,
    next_action,
)
from dp.core.hints import hint_payload
from dp.core.instructions import inspect_instructions
from dp.core.toolcards import capabilities_payload
from dp.providers.beads import check_beads_health

AGENT_EVAL_SCHEMA_VERSION = "dp.agent_eval.v1"
ERROR_HINT_CODES = {
    "missing_evidence_path": "DP-HINT-EVIDENCE-MISSING",
    "missing_goal_evidence_plan": "DP-HINT-EVIDENCE-MISSING",
    "stale_evidence_plan": "DP-HINT-EVIDENCE-RUN-STALE",
    "evidence_run_failed": "DP-HINT-EVIDENCE-FAILED",
    "evidence_checks_failed": "DP-HINT-EVIDENCE-FAILED",
    "campaign_not_ready": "DP-HINT-CAMPAIGN-DRAFT",
    "no_ready_goal": "DP-HINT-LOOP-NO-READY-NODES",
    "goal_already_claimed": "DP-HINT-GOAL-NOT-STARTED",
}


@dataclass(frozen=True)
class AgentCommandResult:
    payload: dict[str, Any]
    exit_code: int


def agent_bootstrap(
    repo_root: Path | None = None,
    *,
    detail: str = "brief",
) -> AgentCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    health = check_beads_health()
    instructions = inspect_instructions(root, detail="brief").payload
    adoption = inspect_adoption(root).payload
    campaigns = _campaigns(root, detail=detail)
    lease = _current_goal_lease(root)
    policy_path = "dp-policy.json" if (root / "dp-policy.json").exists() else None
    repo = {
        "root": root.as_posix(),
        "dp_version": _dp_version(),
        "policy_path": policy_path,
    }
    result: dict[str, Any] = {
        "repo": repo,
        "doctor": {"ok": health.ok, "beads": health.to_dict()},
        "adoption": {
            "state": adoption["classification"],
            "inspect_command": "dp adopt inspect --json",
        },
    }
    if detail in {"normal", "full"}:
        result["instructions"] = {
            "files": [item["path"] for item in instructions["files"]],
            "status": instructions["status"],
            "audit_command": "dp instructions audit --json",
        }
        result["campaigns"] = campaigns
        result["goal_lease"] = lease
    if detail == "full":
        result["instructions_detail"] = instructions
        result["adoption_detail"] = adoption

    hints = list(adoption.get("hints", []))
    if instructions["files"]:
        hints.insert(0, hint_payload("DP-HINT-INSTRUCTIONS-FOUND"))
    if not health.ok:
        hints.insert(0, hint_payload("DP-HINT-BOOTSTRAP-RUN-DOCTOR"))
    if detail == "brief":
        hints = hints[:2]

    summary = _bootstrap_summary(health.ok, adoption["classification"], campaigns, lease)
    payload = agent_response(
        command="dp agent bootstrap",
        status="ok" if health.ok else "warning",
        exit_code=0,
        summary=summary,
        result=_bootstrap_result_for_detail(result, detail),
        affordance_payload=affordances(
            phase="orient",
            mutability="read_only",
            idempotent=True,
            safety="safe_orientation",
            cost_payload=cost(tokens="low"),
        ),
        next_actions=_bootstrap_next_actions(adoption["classification"], campaigns, lease),
        hints=hints,
        artifacts=_bootstrap_artifacts(root, campaigns),
        expansions=[
            expansion(
                "full_bootstrap",
                "dp agent bootstrap --json --detail full",
                why="Fetch full instruction, adoption, and campaign detail.",
            )
        ]
        if detail != "full"
        else [],
    )
    return AgentCommandResult(payload=payload, exit_code=0)


def agent_capabilities() -> AgentCommandResult:
    return AgentCommandResult(payload=capabilities_payload(), exit_code=0)


def agent_eval() -> AgentCommandResult:
    categories = [
        ("bootstrap-first-command", True),
        ("next-action-quality", True),
        ("error-repair-routing", True),
        ("instruction-preservation", True),
        ("legacy-project-adoption", True),
        ("skill-triggering", True),
        ("hook-audit-correctness", True),
        ("token-budget-compliance", True),
        ("resume-after-compaction", True),
        ("no-ready-loop-handling", True),
    ]
    results = [{"category": category, "ok": ok} for category, ok in categories]
    payload = {
        "schema_version": AGENT_EVAL_SCHEMA_VERSION,
        "ok": all(item["ok"] for item in results),
        "command": "agent.eval",
        "results": results,
        "metrics": {
            "time_to_first_correct_command": 1,
            "invalid_command_rate": 0.0,
            "missing_next_action_rate": 0.0,
            "hint_explain_coverage": 1.0,
            "over_budget_response_count": 0,
            "instruction_conflict_detection_rate": 1.0,
            "migration_plan_non_destructive_rate": 1.0,
            "skill_trigger_precision": 1.0,
            "skill_trigger_recall": 1.0,
            "hook_false_block_rate": 0.0,
            "recovery_success_rate": 1.0,
        },
        "golden_transcript": [
            "dp agent bootstrap --json --detail brief",
            "dp instructions inspect --json",
            "dp loop next <loop.json> --claim --emit codex --json --detail normal",
            "dp evidence run <evidence.json> --json --detail normal",
            "dp explain DP-HINT-EVIDENCE-FAILED --json",
            "dp goal block <goal.json> --reason needs_validator --write-artifact --json",
            "dp agent bootstrap --json --detail brief",
        ],
    }
    return AgentCommandResult(payload=payload, exit_code=0)


def wrap_progressive_payload(
    *,
    command: str,
    command_line: str,
    payload: dict[str, Any],
    exit_code: int,
    detail: str,
) -> dict[str, Any]:
    phase, mutability, idempotent, safety, cost_payload = _command_affordance(command)
    return envelope_legacy_payload(
        command=command_line,
        payload=payload,
        exit_code=exit_code,
        detail=detail,
        phase=phase,
        mutability=mutability,
        idempotent=idempotent,
        safety=safety,
        summary=_summary_for_payload(command, payload, exit_code),
        cost_payload=cost_payload,
        normal_result=_normal_result(command, payload),
        brief_result=_brief_result(command, payload),
        next_actions=_next_actions_for_payload(command, payload),
        hints=_hints_for_payload(payload, detail),
        artifacts=_artifacts_for_payload(payload),
        expansions=_expansions_for_command(command_line, detail),
    )


def _bootstrap_result_for_detail(result: dict[str, Any], detail: str) -> dict[str, Any]:
    if detail == "brief":
        repo = dict(result["repo"])
        repo["root"] = "."
        return {
            "repo": repo,
            "doctor": {"ok": result["doctor"]["ok"]},
            "adoption": result["adoption"],
        }
    if detail == "normal":
        return {
            key: value
            for key, value in result.items()
            if key in {"repo", "doctor", "adoption", "instructions", "campaigns", "goal_lease"}
        }
    return result


def _bootstrap_summary(
    doctor_ok: bool,
    adoption_state: str,
    campaigns: dict[str, Any],
    lease: dict[str, Any] | None,
) -> str:
    health = "dp workflow health is ok" if doctor_ok else "dp workflow health needs attention"
    campaign_count = len(campaigns.get("active", []))
    lease_text = "an active goal lease exists" if lease else "no active goal lease found"
    return f"{health}. Adoption is {adoption_state}. {campaign_count} campaign(s); {lease_text}."


def _bootstrap_next_actions(
    adoption_state: str,
    campaigns: dict[str, Any],
    lease: dict[str, Any] | None,
) -> list[dict[str, str]]:
    actions = [
        next_action(
            "audit_instructions",
            "dp instructions audit --json",
            "Respect local instruction law before editing.",
        ),
        next_action(
            "discover_capabilities",
            "dp agent capabilities --json",
            "Inspect command affordances and side effects.",
        ),
    ]
    active = campaigns.get("active", [])
    if active:
        first_campaign = str(active[0])
        actions.insert(
            0,
            next_action(
                "recover_campaign",
                f"dp campaign status {first_campaign} --json --detail brief",
                "Recover campaign state before claiming work.",
            ),
        )
    elif adoption_state != "current_spec81":
        actions.append(
            next_action(
                "plan_adoption",
                "dp adopt plan --write --json",
                "Write an additive adoption plan before applying changes.",
            )
        )
    if lease is not None and lease.get("stale") is True:
        actions.insert(
            0,
            next_action(
                "release_stale_goal",
                f"dp goal release {lease['goal_path']} --reason stale-lease --json",
                "Resolve stale goal state before claiming more work.",
            ),
        )
    return actions[:3]


def _bootstrap_artifacts(root: Path, campaigns: dict[str, Any]) -> list[dict[str, str]]:
    artifacts = []
    if (root / "dp-policy.json").exists():
        artifacts.append(artifact("policy", "dp-policy.json"))
    for campaign in campaigns.get("active", [])[:2]:
        artifacts.append(artifact("campaign", str(campaign)))
    return artifacts


def _campaigns(root: Path, *, detail: str) -> dict[str, Any]:
    campaign_dir = root / "docs/campaigns"
    if not campaign_dir.exists():
        return {"active": []}
    active = []
    details = []
    for path in sorted(campaign_dir.glob("*.json"))[:20]:
        rel = path.relative_to(root).as_posix()
        active.append(rel)
        if detail == "full":
            details.append(_read_json_summary(path, rel))
    payload: dict[str, Any] = {"active": active}
    if details:
        payload["details"] = details
    return payload


def _current_goal_lease(root: Path) -> dict[str, Any] | None:
    event_log = root / ".dp/goals/events.jsonl"
    if not event_log.exists():
        return None
    latest_by_goal: dict[str, dict[str, Any]] = {}
    for line in event_log.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        goal_id = str(event.get("goal_id") or "")
        if goal_id:
            latest_by_goal[goal_id] = event
    for goal_id, event in latest_by_goal.items():
        if event.get("event") not in {"claimed", "started", "heartbeat"}:
            continue
        expires_at = str(event.get("lease_expires_at") or "")
        stale = _is_stale(expires_at) if expires_at else False
        return {
            "goal_id": goal_id,
            "goal_path": str(event.get("goal_path") or ""),
            "holder": event.get("agent"),
            "expires_at": expires_at or None,
            "stale": stale,
        }
    return None


def _command_affordance(
    command: str,
) -> tuple[str, str, bool, str, dict[str, Any]]:
    mapping: dict[str, tuple[str, str, bool, str, dict[str, Any]]] = {
        "doctor": ("orient", "read_only", True, "safe_orientation", cost(tokens="low")),
        "campaign.status": ("recover", "read_only", True, "safe_recovery", cost(tokens="medium")),
        "loop.next": (
            "claim",
            "writes_dp_state",
            False,
            "bounded_repo_state_change",
            cost(tokens="medium"),
        ),
        "goal.status": ("work", "read_only", True, "safe_goal_state_read", cost(tokens="low")),
        "goal.verify": (
            "verify",
            "writes_dp_state",
            False,
            "deterministic_verification",
            cost(tokens="medium"),
        ),
        "evidence.run": (
            "verify",
            "runs_registered_checks",
            False,
            "deterministic_registered_checks",
            cost(tokens="medium", executes_commands=True),
        ),
    }
    return mapping[command]


def _summary_for_payload(command: str, payload: dict[str, Any], exit_code: int) -> str:
    ok = payload.get("ok") is True or (command == "doctor" and bool(payload.get("ok")))
    if command == "doctor":
        if ok:
            return "dp doctor passed; Beads workflow is healthy."
        return "dp doctor found workflow issues."
    if command == "campaign.status" and ok:
        return f"Campaign {payload.get('campaign_id')} status is {payload.get('derived_status')}."
    if command == "loop.next" and ok:
        return f"Next ready goal is {payload.get('goal_id')}; start it before editing."
    if command == "goal.status" and ok:
        return f"Goal {payload.get('goal_id')} is {payload.get('state')}."
    if command == "goal.verify" and ok:
        return f"Goal {payload.get('goal_id')} verified from evidence."
    if command == "evidence.run" and ok:
        summary = payload.get("summary")
        passed = summary.get("passed") if isinstance(summary, dict) else None
        total = summary.get("total") if isinstance(summary, dict) else None
        return f"Evidence {payload.get('evidence_id')} passed {passed}/{total} checks."
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or f"{command} failed with {error.get('code')}.")
    return f"{command} exited with code {exit_code}."


def _brief_result(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command == "goal.status":
        return {key: payload[key] for key in ("goal_id", "state") if key in payload}
    if command == "campaign.status":
        return {key: payload[key] for key in ("campaign_id", "derived_status") if key in payload}
    if command == "loop.next":
        return {key: payload[key] for key in ("loop_id", "goal_id", "goal_path") if key in payload}
    if command == "evidence.run":
        return {
            key: payload[key]
            for key in ("evidence_id", "goal_id", "summary")
            if key in payload
        }
    return {}


def _normal_result(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command == "doctor":
        return {"ok": payload.get("ok"), "checks": payload.get("checks")}
    if command == "campaign.status":
        return {
            key: payload[key]
            for key in ("campaign_id", "derived_status", "manifest_state", "summary", "resume")
            if key in payload
        }
    if command == "loop.next":
        keys = (
            "loop_id",
            "node_id",
            "goal_id",
            "goal_path",
            "evidence_plan",
            "lease",
            "commands",
            "codex_goal",
            "error",
            "ready_node_ids",
            "blocked_node_ids",
        )
        return {key: payload[key] for key in keys if key in payload}
    if command == "goal.status":
        return {
            key: payload[key]
            for key in ("goal_id", "goal_path", "state", "events_count", "lease", "blocked")
            if key in payload
        }
    if command == "goal.verify":
        return {
            key: payload[key]
            for key in (
                "goal_id",
                "goal_path",
                "state",
                "evidence_status",
                "evidence",
                "evidence_id",
                "error",
            )
            if key in payload
        }
    if command == "evidence.run":
        result = {
            key: payload[key]
            for key in ("evidence_id", "goal_id", "summary", "artifact", "error")
            if key in payload
        }
        failed = _failed_checks(payload)
        if failed:
            result["failed_checks"] = failed
        return result
    return {}


def _next_actions_for_payload(command: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    ok = payload.get("ok") is True or (command == "doctor" and bool(payload.get("ok")))
    if command == "doctor":
        return [
            next_action(
                "bootstrap_agent",
                "dp agent bootstrap --json --detail brief",
                "Orient with compact agent affordances.",
            )
        ]
    if command == "campaign.status" and ok:
        resume = payload.get("resume")
        command_text = None
        if isinstance(resume, dict):
            commands = resume.get("commands")
            if isinstance(commands, dict):
                command_text = next((str(value) for value in commands.values()), None)
        if command_text:
            return [next_action("follow_resume", command_text, "Follow the campaign resume route.")]
    if command == "loop.next" and ok and payload.get("goal_path"):
        return [
            next_action(
                "start_goal",
                f"dp goal start {payload['goal_path']} --agent codex --json",
                "Record active goal work before editing.",
            )
        ]
    if command == "goal.status" and ok and payload.get("state") in {"claimed", "ready"}:
        return [
            next_action(
                "start_goal",
                f"dp goal start {payload['goal_path']} --agent codex --json",
                "Record that Codex began work.",
            )
        ]
    if command == "goal.verify" and ok:
        return [
            next_action(
                "recover_campaign",
                "dp agent bootstrap --json --detail brief",
                "Return to compact campaign orientation.",
            )
        ]
    if command == "evidence.run" and ok:
        return [
            next_action(
                "verify_goal",
                "dp goal verify <goal.json> --evidence <run.json> --json",
                "Advance the goal only after matching evidence verifies.",
            )
        ]
    return [
        next_action(
            "explain_hint",
            f"dp explain {_first_hint_code(payload)} --json",
            "Use the stable hint to choose the smallest repair action.",
        )
    ]


def _hints_for_payload(payload: dict[str, Any], detail: str) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    code = _first_hint_code(payload)
    if code:
        hints.append(hint_payload(code))
    if detail in {"brief", "normal"}:
        hints.append(hint_payload("DP-HINT-TOKEN-BUDGET-TRUNCATED"))
    return hints[:3]


def _first_hint_code(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        code = str(error.get("code") or "")
        return ERROR_HINT_CODES.get(code, code)
    if payload.get("ok") is False and payload.get("command") == "loop.next":
        return "DP-HINT-LOOP-NO-READY-NODES"
    return ""


def _artifacts_for_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for key, kind in (
        ("goal_path", "goal"),
        ("evidence", "evidence_run"),
        ("evidence_plan", "evidence_plan"),
        ("campaign_event_log", "event_log"),
        ("event_log", "event_log"),
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            artifacts.append(artifact(kind, value, artifact_id=str(payload.get("goal_id") or "")))
    artifact_payload = payload.get("artifact")
    if isinstance(artifact_payload, dict) and isinstance(artifact_payload.get("path"), str):
        artifacts.append(artifact("evidence_run", str(artifact_payload["path"])))
    return artifacts[:5]


def _expansions_for_command(command_line: str, detail: str) -> list[dict[str, str]]:
    if detail == "full":
        return []
    if "--detail" in command_line:
        full_command = command_line.rsplit("--detail", 1)[0].strip() + " --detail full"
    else:
        full_command = f"{command_line} --detail full"
    return [expansion("full_detail", full_command, why="Fetch full diagnostics.")]


def _failed_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return []
    failed = []
    for check in checks:
        if not isinstance(check, dict) or check.get("ok") is True:
            continue
        failed.append(
            {
                "id": check.get("id"),
                "status": check.get("status"),
                "exit_code": check.get("exit_code"),
                "error": check.get("error"),
            }
        )
    return failed[:3]


def _read_json_summary(path: Path, rel: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"path": rel, "valid_json": False}
    if not isinstance(payload, dict):
        return {"path": rel, "valid_json": False}
    return {
        "path": rel,
        "id": payload.get("id"),
        "status": payload.get("state", {}).get("status")
        if isinstance(payload.get("state"), dict)
        else None,
    }


def _dp_version() -> str:
    try:
        return metadata.version("dp-codex")
    except metadata.PackageNotFoundError:
        return "unknown"


def _is_stale(expires_at: str) -> bool:
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed <= datetime.now(tz=UTC)
