from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dp.core.events import append_jsonl_event, read_jsonl_events
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
    event = _base_event("blocked", goal_id=goal_id, goal_path=goal_path, timestamp=now)
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
            "command": "goal.block",
            "event_log": append_result.path,
            **state.to_dict(),
        },
        exit_code=0,
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
                "Evidence recorded; behavioral evidence verification is not implemented yet."
            ),
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
        elif event_type == "released":
            state = "released"
            lease = None
        elif event_type == "evidence_pending":
            state = "evidence_pending"
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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_event_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _is_sane_relative_path(value: str) -> bool:
    return bool(value) and not value.startswith(("/", "~", "-")) and ".." not in Path(value).parts
