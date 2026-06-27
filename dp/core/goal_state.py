from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from dp.core.blocker_routing import route_blocker_artifact
from dp.core.events import append_jsonl_event, read_jsonl_events
from dp.core.evidence_lint import lint_evidence_file
from dp.core.goal_lint import GoalLintReport, lint_goal_file

# @trace SPEC-80.02
GOAL_EVENT_SCHEMA_VERSION = "0.1"
DEFAULT_GOAL_EVENT_LOG = Path(".dp/goals/events.jsonl")
KNOWN_BLOCK_REASONS = frozenset(
    {
        "needs_specification",
        "needs_decision",
        "needs_validator",
        "unsafe_scope",
        "budget_exhausted",
    }
)


@dataclass(frozen=True)
class GoalCommandResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class GoalState:
    goal_id: str
    goal_path: str
    state: str
    events_count: int
    lease: dict[str, Any] | None
    blocked: dict[str, Any] | None
    last_event: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_path": self.goal_path,
            "state": self.state,
            "events_count": self.events_count,
            "lease": self.lease,
            "blocked": self.blocked,
            "last_event": self.last_event,
        }


def goal_status(goal_path: Path, *, event_log: Path = DEFAULT_GOAL_EVENT_LOG) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.status", lint_result.report, lint_result.exit_code)

    goal_id = _require_goal_id(lint_result.report)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=_utc_now(),
    )
    payload = {"ok": True, "command": "goal.status", **state.to_dict()}
    return GoalCommandResult(payload=payload, exit_code=0)


def claim_goal(
    goal_path: Path,
    *,
    agent: str,
    lease: str,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.claim", lint_result.report, lint_result.exit_code)
    if not agent.strip():
        return _usage_error("goal.claim", "agent_required", "$.agent", "Agent must be non-empty.")

    try:
        lease_delta = parse_lease_duration(lease)
    except ValueError as exc:
        return _usage_error("goal.claim", "invalid_lease", "$.lease", str(exc))

    now = _utc_now()
    goal_id = _require_goal_id(lint_result.report)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    active_holder = _active_lease_holder(state)
    if active_holder is not None and active_holder != agent:
        payload = {
            "ok": False,
            "command": "goal.claim",
            "error": {
                "code": "goal_already_claimed",
                "message": f"Goal is already claimed by {active_holder}.",
            },
            **state.to_dict(),
        }
        return GoalCommandResult(payload=payload, exit_code=1)

    event = _base_event(
        "claimed",
        goal_id=goal_id,
        goal_path=goal_path,
        timestamp=now,
        agent=agent,
        lease_expires_at=_format_time(now + lease_delta),
    )
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    return GoalCommandResult(
        payload={
            "ok": True,
            "command": "goal.claim",
            "event_log": append_result.path,
            **state.to_dict(),
        },
        exit_code=0,
    )


def start_goal(
    goal_path: Path,
    *,
    agent: str,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.start", lint_result.report, lint_result.exit_code)
    if not agent.strip():
        return _usage_error("goal.start", "agent_required", "$.agent", "Agent must be non-empty.")

    now = _utc_now()
    goal_id = _require_goal_id(lint_result.report)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    active_holder = _active_lease_holder(state)
    if active_holder is not None and active_holder != agent:
        return GoalCommandResult(
            payload={
                "ok": False,
                "command": "goal.start",
                "error": {
                    "code": "goal_claimed_by_another_agent",
                    "message": f"Goal is claimed by {active_holder}.",
                },
                **state.to_dict(),
            },
            exit_code=1,
        )

    event = _base_event("started", goal_id=goal_id, goal_path=goal_path, timestamp=now, agent=agent)
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    return GoalCommandResult(
        payload={
            "ok": True,
            "command": "goal.start",
            "event_log": append_result.path,
            **state.to_dict(),
        },
        exit_code=0,
    )


def heartbeat_goal(
    goal_path: Path,
    *,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.heartbeat", lint_result.report, lint_result.exit_code)

    now = _utc_now()
    goal_id = _require_goal_id(lint_result.report)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    active_holder = _active_lease_holder(state)
    if active_holder is None:
        return GoalCommandResult(
            payload={
                "ok": False,
                "command": "goal.heartbeat",
                "error": {
                    "code": "goal_not_claimed",
                    "message": "Heartbeat requires an active non-stale claim.",
                },
                **state.to_dict(),
            },
            exit_code=1,
        )

    event = _base_event(
        "heartbeat",
        goal_id=goal_id,
        goal_path=goal_path,
        timestamp=now,
        agent=active_holder,
    )
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    return GoalCommandResult(
        payload={
            "ok": True,
            "command": "goal.heartbeat",
            "event_log": append_result.path,
            **state.to_dict(),
        },
        exit_code=0,
    )


def block_goal(
    goal_path: Path,
    *,
    reason: str,
    write_artifact: bool = False,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.block", lint_result.report, lint_result.exit_code)
    if reason not in KNOWN_BLOCK_REASONS:
        return _usage_error(
            "goal.block",
            "unknown_block_reason",
            "$.reason",
            "Block reason must be one of: budget_exhausted, needs_decision, "
            "needs_specification, needs_validator, unsafe_scope.",
        )

    now = _utc_now()
    goal_id = _require_goal_id(lint_result.report)
    routing_result = None
    if write_artifact:
        contract = _read_json_object(goal_path)
        routing_result = route_blocker_artifact(
            goal_path=goal_path,
            goal_contract=contract,
            reason=reason,
        )

    event = _base_event("blocked", goal_id=goal_id, goal_path=goal_path, timestamp=now)
    event["reason"] = reason
    if routing_result is not None:
        event["routing"] = routing_result.routing
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    ok = routing_result is None or routing_result.error is None
    payload = {
        "ok": ok,
        "command": "goal.block",
        "event_log": append_result.path,
        **state.to_dict(),
    }
    if routing_result is not None:
        payload["routing"] = routing_result.routing
        if routing_result.error is not None:
            payload["error"] = routing_result.error
    return GoalCommandResult(
        payload=payload,
        exit_code=0 if routing_result is None else routing_result.exit_code,
    )


def release_goal(
    goal_path: Path,
    *,
    reason: str,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.release", lint_result.report, lint_result.exit_code)
    if not reason.strip():
        return _usage_error(
            "goal.release",
            "release_reason_required",
            "$.reason",
            "Release requires a non-empty reason.",
        )

    now = _utc_now()
    goal_id = _require_goal_id(lint_result.report)
    event = _base_event("released", goal_id=goal_id, goal_path=goal_path, timestamp=now)
    event["reason"] = reason
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    return GoalCommandResult(
        payload={
            "ok": True,
            "command": "goal.release",
            "event_log": append_result.path,
            **state.to_dict(),
        },
        exit_code=0,
    )


def complete_goal(
    goal_path: Path,
    *,
    evidence_path: Path,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.complete", lint_result.report, lint_result.exit_code)
    if not _is_sane_relative_path(evidence_path.as_posix()):
        return _usage_error(
            "goal.complete",
            "invalid_evidence_path",
            "$.evidence",
            "Evidence path must be a sane relative path.",
        )
    if not evidence_path.exists():
        return _usage_error(
            "goal.complete",
            "missing_evidence_path",
            "$.evidence",
            f"Evidence path does not exist: {evidence_path.as_posix()}",
        )

    now = _utc_now()
    goal_id = _require_goal_id(lint_result.report)
    event = _base_event(
        "evidence_pending",
        goal_id=goal_id,
        goal_path=goal_path,
        timestamp=now,
        evidence=evidence_path.as_posix(),
    )
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    return GoalCommandResult(
        payload={
            "ok": True,
            "command": "goal.complete",
            "event_log": append_result.path,
            "evidence_status": "pending_verification",
            "message": (
                "Evidence recorded; run dp goal verify with a matching evidence run to verify."
            ),
            **state.to_dict(),
        },
        exit_code=0,
    )


# @trace SPEC-80.10
def verify_goal(
    goal_path: Path,
    *,
    evidence_path: Path,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
) -> GoalCommandResult:
    lint_result = lint_goal_file(goal_path)
    if lint_result.exit_code != 0:
        return _lint_failure_payload("goal.verify", lint_result.report, lint_result.exit_code)
    if not _is_sane_relative_path(evidence_path.as_posix()):
        return _usage_error(
            "goal.verify",
            "invalid_evidence_path",
            "$.evidence",
            "Evidence path must be a sane relative path.",
        )
    if not evidence_path.exists():
        return _usage_error(
            "goal.verify",
            "missing_evidence_path",
            "$.evidence",
            f"Evidence path does not exist: {evidence_path.as_posix()}",
        )

    goal_id = _require_goal_id(lint_result.report)
    contract = _read_json_object(goal_path)
    evidence_run = _load_evidence_run(evidence_path)
    if isinstance(evidence_run, GoalCommandResult):
        return evidence_run

    goal_evidence_plan = _goal_evidence_plan_path(contract)
    if goal_evidence_plan is None:
        return _verification_failure(
            "missing_goal_evidence_plan",
            "$.evidence.evidence_plan",
            "GoalContract must reference an evidence_plan before evidence can verify it.",
            goal_id=goal_id,
            exit_code=1,
        )

    evidence_plan_path = Path(goal_evidence_plan)
    evidence_plan_payload = _validate_evidence_run_against_goal(
        evidence_run,
        goal_id=goal_id,
        goal_evidence_plan=goal_evidence_plan,
        evidence_plan_path=evidence_plan_path,
    )
    if isinstance(evidence_plan_payload, GoalCommandResult):
        return evidence_plan_payload

    now = _utc_now()
    event = _base_event(
        "verified",
        goal_id=goal_id,
        goal_path=goal_path,
        timestamp=now,
        evidence=evidence_path.as_posix(),
        evidence_sha256=_file_sha256(evidence_path),
        evidence_id=str(evidence_run["evidence_id"]),
        evidence_plan=goal_evidence_plan,
        evidence_plan_sha256=_file_sha256(evidence_plan_path),
    )
    append_result = append_jsonl_event(event_log, event)
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=goal_path,
        event_log=event_log,
        now=now,
    )
    return GoalCommandResult(
        payload={
            "ok": True,
            "command": "goal.verify",
            "event_log": append_result.path,
            "evidence_status": "verified",
            "evidence": evidence_path.as_posix(),
            "evidence_id": evidence_run["evidence_id"],
            "evidence_plan": goal_evidence_plan,
            "evidence_plan_sha256": _file_sha256(evidence_plan_path),
            "message": "Evidence run verified; goal state advanced to verified.",
            **state.to_dict(),
        },
        exit_code=0,
    )


def reconstruct_goal_state(
    *,
    goal_id: str,
    goal_path: Path,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
    now: datetime | None = None,
) -> GoalState:
    effective_now = now or _utc_now()
    events = [
        event
        for event in read_jsonl_events(event_log)
        if event.get("goal_id") == goal_id
        and event.get("schema_version") == GOAL_EVENT_SCHEMA_VERSION
    ]

    state = "ready"
    lease: dict[str, Any] | None = None
    blocked: dict[str, Any] | None = None

    for event in events:
        event_type = str(event.get("event", ""))
        if event_type == "claimed":
            expires_at = str(event.get("lease_expires_at", ""))
            stale = _parse_event_time(expires_at) <= effective_now
            lease = {
                "holder": event.get("agent"),
                "expires_at": expires_at,
                "stale": stale,
            }
            state = "released" if stale else "claimed"
            blocked = None
        elif event_type == "started":
            if lease is not None and bool(lease.get("stale")):
                lease = None
            state = "started"
            blocked = None
        elif event_type == "heartbeat":
            state = "pursuing"
        elif event_type == "blocked":
            state = "blocked"
            blocked = {
                "reason": event.get("reason"),
                "timestamp": event.get("timestamp"),
            }
            if "routing" in event:
                blocked["routing"] = event.get("routing")
        elif event_type == "released":
            state = "released"
            lease = None
        elif event_type == "evidence_pending":
            state = "evidence_pending"
            blocked = None
        elif event_type == "verified":
            state = "verified"
            lease = None
            blocked = None

    return GoalState(
        goal_id=goal_id,
        goal_path=goal_path.as_posix(),
        state=state,
        events_count=len(events),
        lease=lease,
        blocked=blocked,
        last_event=events[-1] if events else None,
    )


def parse_lease_duration(value: str) -> timedelta:
    raw = value.strip().lower()
    if len(raw) < 2:
        raise ValueError("Lease must use a duration like 30m, 2h, or 1d.")
    number_text = raw[:-1]
    unit = raw[-1]
    try:
        amount = int(number_text)
    except ValueError as exc:
        raise ValueError("Lease must use an integer duration like 30m, 2h, or 1d.") from exc
    if amount <= 0:
        raise ValueError("Lease duration must be greater than zero.")
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError("Lease unit must be one of m, h, or d.")


def _lint_failure_payload(
    command: str,
    report: GoalLintReport,
    exit_code: int,
) -> GoalCommandResult:
    return GoalCommandResult(
        payload={
            "ok": False,
            "command": command,
            "lint": report.to_dict(),
        },
        exit_code=exit_code,
    )


def _usage_error(command: str, code: str, path: str, message: str) -> GoalCommandResult:
    return GoalCommandResult(
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


def _verification_failure(
    code: str,
    path: str,
    message: str,
    *,
    goal_id: str | None = None,
    exit_code: int = 1,
) -> GoalCommandResult:
    payload: dict[str, Any] = {
        "ok": False,
        "command": "goal.verify",
        "error": {
            "code": code,
            "path": path,
            "message": message,
        },
    }
    if goal_id is not None:
        payload["goal_id"] = goal_id
    return GoalCommandResult(payload=payload, exit_code=exit_code)


def _require_goal_id(report: GoalLintReport) -> str:
    if report.goal_id is None:
        raise ValueError("Valid goal lint report unexpectedly lacks goal_id.")
    return report.goal_id


def _active_lease_holder(state: GoalState) -> str | None:
    if state.lease is None or bool(state.lease.get("stale")):
        return None
    holder = state.lease.get("holder")
    return holder if isinstance(holder, str) and holder else None


def _base_event(
    event_type: str,
    *,
    goal_id: str,
    goal_path: Path,
    timestamp: datetime,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "schema_version": GOAL_EVENT_SCHEMA_VERSION,
        "event": event_type,
        "goal_id": goal_id,
        "goal_path": goal_path.as_posix(),
        "timestamp": _format_time(timestamp),
        **fields,
    }


def _load_evidence_run(path: Path) -> dict[str, Any] | GoalCommandResult:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _verification_failure(
            "malformed_evidence_run",
            "$",
            f"Evidence run is not valid JSON: line {exc.lineno} column {exc.colno}.",
            exit_code=2,
        )
    if not isinstance(payload, dict):
        return _verification_failure(
            "invalid_evidence_run",
            "$",
            "Evidence run must be a JSON object emitted by dp evidence run.",
            exit_code=2,
        )
    if payload.get("command") != "evidence.run":
        return _verification_failure(
            "invalid_evidence_run",
            "$.command",
            "Evidence must be a dp evidence run output, not an agent self-report.",
            exit_code=2,
        )
    return payload


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Valid GoalContract unexpectedly loaded as non-object.")
    return payload


def _goal_evidence_plan_path(contract: dict[str, Any]) -> str | None:
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        return None
    path = evidence.get("evidence_plan")
    if not isinstance(path, str) or not path.strip():
        return None
    return path.strip()


def _validate_evidence_run_against_goal(
    evidence_run: dict[str, Any],
    *,
    goal_id: str,
    goal_evidence_plan: str,
    evidence_plan_path: Path,
) -> dict[str, Any] | GoalCommandResult:
    evidence_plan_source = evidence_run.get("evidence_plan")
    if not isinstance(evidence_plan_source, dict):
        return _verification_failure(
            "invalid_evidence_run",
            "$.evidence_plan",
            "Evidence run must record evidence_plan path and sha256.",
            goal_id=goal_id,
            exit_code=2,
        )

    run_plan_path = _non_empty_string(evidence_plan_source.get("path"))
    run_plan_sha = _non_empty_string(evidence_plan_source.get("sha256"))
    if run_plan_path is None or not _is_sane_relative_path(run_plan_path):
        return _verification_failure(
            "invalid_evidence_run",
            "$.evidence_plan.path",
            "Evidence run evidence_plan.path must be a sane relative path.",
            goal_id=goal_id,
            exit_code=2,
        )
    if run_plan_sha is None or not _is_sha256_digest(run_plan_sha):
        return _verification_failure(
            "invalid_evidence_run",
            "$.evidence_plan.sha256",
            "Evidence run evidence_plan.sha256 must be a sha256 digest.",
            goal_id=goal_id,
            exit_code=2,
        )

    if evidence_run.get("goal_id") != goal_id:
        return _verification_failure(
            "goal_id_mismatch",
            "$.goal_id",
            "Evidence run goal_id must match the GoalContract id.",
            goal_id=goal_id,
        )
    if run_plan_path != goal_evidence_plan:
        return _verification_failure(
            "evidence_plan_mismatch",
            "$.evidence_plan.path",
            "Evidence run must come from the GoalContract evidence_plan.",
            goal_id=goal_id,
        )
    if not evidence_plan_path.exists():
        return _verification_failure(
            "missing_evidence_plan",
            "$.evidence_plan.path",
            f"EvidencePlan does not exist: {goal_evidence_plan}",
            goal_id=goal_id,
        )

    lint_result = lint_evidence_file(evidence_plan_path)
    if lint_result.exit_code != 0:
        return _verification_failure(
            "invalid_evidence_plan",
            "$.evidence_plan.path",
            "Current EvidencePlan must pass deterministic lint.",
            goal_id=goal_id,
        )
    if lint_result.report.goal_id != goal_id:
        return _verification_failure(
            "evidence_plan_goal_mismatch",
            "$.evidence_plan.goal_id",
            "Current EvidencePlan goal_id must match the GoalContract id.",
            goal_id=goal_id,
        )
    if _file_sha256(evidence_plan_path) != run_plan_sha:
        return _verification_failure(
            "stale_evidence_plan",
            "$.evidence_plan.sha256",
            "EvidencePlan has changed since the evidence run was produced.",
            goal_id=goal_id,
        )

    plan_payload = _read_json_object(evidence_plan_path)
    evidence_id = _non_empty_string(plan_payload.get("id"))
    if evidence_run.get("evidence_id") != evidence_id:
        return _verification_failure(
            "evidence_id_mismatch",
            "$.evidence_id",
            "Evidence run evidence_id must match the current EvidencePlan id.",
            goal_id=goal_id,
        )

    run_lint = evidence_run.get("lint")
    if not isinstance(run_lint, dict) or run_lint.get("valid") is not True:
        return _verification_failure(
            "invalid_evidence_run",
            "$.lint",
            "Evidence run must include a valid lint report.",
            goal_id=goal_id,
            exit_code=2,
        )
    if run_lint.get("goal_id") != goal_id or run_lint.get("evidence_id") != evidence_id:
        return _verification_failure(
            "invalid_evidence_run",
            "$.lint",
            "Evidence run lint report must match goal_id and evidence_id.",
            goal_id=goal_id,
            exit_code=2,
        )

    run_failure = _validate_successful_run_shape(evidence_run)
    if run_failure is not None:
        return _verification_failure(
            "evidence_run_failed",
            run_failure,
            "Evidence run did not pass all checks and typed assertions.",
            goal_id=goal_id,
        )

    return plan_payload


def _validate_successful_run_shape(evidence_run: dict[str, Any]) -> str | None:
    if evidence_run.get("ok") is not True or evidence_run.get("error") is not None:
        return "$.ok"
    checks = evidence_run.get("checks")
    if not isinstance(checks, list) or not checks:
        return "$.checks"

    passed = 0
    failed = 0
    timed_out = 0
    errored = 0
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            return f"$.checks[{index}]"
        status = check.get("status")
        if check.get("ok") is not True or status != "passed":
            return f"$.checks[{index}]"
        passed += 1
        assertions = check.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            return f"$.checks[{index}].assertions"
        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict) or assertion.get("ok") is not True:
                return f"$.checks[{index}].assertions[{assertion_index}]"

    summary = evidence_run.get("summary")
    if not isinstance(summary, dict):
        return "$.summary"
    failed = sum(
        1 for check in checks if isinstance(check, dict) and check.get("status") == "failed"
    )
    timed_out = sum(
        1 for check in checks if isinstance(check, dict) and check.get("status") == "timed_out"
    )
    errored = sum(
        1 for check in checks if isinstance(check, dict) and check.get("status") == "error"
    )
    expected_summary = {
        "total": len(checks),
        "passed": passed,
        "failed": failed,
        "timed_out": timed_out,
        "errored": errored,
    }
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        return "$.summary"
    return None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_event_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _is_sane_relative_path(value: str) -> bool:
    return bool(value) and not value.startswith(("/", "~", "-")) and ".." not in Path(value).parts


def _non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _is_sha256_digest(value: str) -> bool:
    prefix = "sha256:"
    if not value.startswith(prefix) or len(value) != len(prefix) + 64:
        return False
    return all(character in "0123456789abcdef" for character in value[len(prefix) :])
