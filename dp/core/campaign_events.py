from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dp.core.events import EventAppendResult, append_jsonl_event, read_jsonl_events

# @trace SPEC-80.15
CAMPAIGN_EVENT_SCHEMA_VERSION = "0.1"
DEFAULT_CAMPAIGN_EVENT_LOG = Path(".dp/campaigns/events.jsonl")


def append_campaign_handoff_event(
    *,
    event_log: Path = DEFAULT_CAMPAIGN_EVENT_LOG,
    campaign_id: str,
    campaign_path: Path,
    loop_id: str,
    node_id: str,
    goal_id: str,
    goal_path: str,
    agent: str,
    lease: dict[str, Any] | None,
) -> EventAppendResult:
    event: dict[str, Any] = {
        "schema_version": CAMPAIGN_EVENT_SCHEMA_VERSION,
        "event": "handoff_claimed",
        "campaign_id": campaign_id,
        "campaign_path": campaign_path.as_posix(),
        "timestamp": _format_time(_utc_now()),
        "loop_id": loop_id,
        "node_id": node_id,
        "goal_id": goal_id,
        "goal_path": goal_path,
        "agent": agent,
    }
    if isinstance(lease, dict):
        event["lease"] = lease
    return append_jsonl_event(event_log, event)


def campaign_event_summary(
    *,
    campaign_id: str,
    event_log: Path = DEFAULT_CAMPAIGN_EVENT_LOG,
) -> dict[str, Any]:
    events = [
        event
        for event in read_jsonl_events(event_log)
        if event.get("schema_version") == CAMPAIGN_EVENT_SCHEMA_VERSION
        and event.get("campaign_id") == campaign_id
    ]
    return {
        "event_log": event_log.as_posix(),
        "events_count": len(events),
        "last_event": events[-1] if events else None,
    }


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
