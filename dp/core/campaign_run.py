from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.campaign_events import (
    DEFAULT_CAMPAIGN_EVENT_LOG,
    append_campaign_handoff_event,
)
from dp.core.campaign_manifest import CampaignCommandResult, campaign_status
from dp.core.goal_state import DEFAULT_GOAL_EVENT_LOG
from dp.core.loop_ledger import loop_next

# @trace SPEC-80.13
SUPPORTED_SUPERVISED_DRIVERS = frozenset({"codex"})


@dataclass(frozen=True)
class CampaignRunResult:
    payload: dict[str, Any]
    exit_code: int


def run_campaign_once(
    campaign_path: Path,
    *,
    driver: str,
    supervised: bool,
    agent: str,
    lease: str,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
    campaign_event_log: Path = DEFAULT_CAMPAIGN_EVENT_LOG,
) -> CampaignRunResult:
    if not supervised:
        return _usage_error(
            driver=driver,
            supervised=supervised,
            code="supervised_required",
            path="$.supervised",
            message="dp campaign run requires --supervised in this slice.",
        )
    if driver not in SUPPORTED_SUPERVISED_DRIVERS:
        return _usage_error(
            driver=driver,
            supervised=supervised,
            code="unsupported_driver",
            path="$.driver",
            message="Only the codex supervised driver is supported.",
        )
    if not agent.strip():
        return _usage_error(
            driver=driver,
            supervised=supervised,
            code="agent_required",
            path="$.agent",
            message="Agent must be non-empty.",
        )

    status_result = campaign_status(
        campaign_path,
        event_log=event_log,
        campaign_event_log=campaign_event_log,
    )
    campaign_id = _campaign_id_from_status(status_result.payload)
    if status_result.exit_code != 0:
        return CampaignRunResult(
            payload={
                **_base_payload(
                    driver=driver,
                    supervised=supervised,
                    campaign_id=campaign_id,
                ),
                "ok": False,
                "status": status_result.payload,
                "error": {
                    "code": "campaign_status_failed",
                    "message": "Campaign status could not be reconstructed.",
                    "path": "$.campaign",
                },
                "stop_conditions": _stop_conditions(),
            },
            exit_code=status_result.exit_code,
        )

    resume = _resume_from_status(status_result.payload)
    if resume is not None and resume.get("action") == "resume_claimed_goal":
        return CampaignRunResult(
            payload={
                **_base_payload(
                    driver=driver,
                    supervised=supervised,
                    campaign_id=campaign_id,
                ),
                "ok": True,
                "status": status_result.payload,
                "next": resume,
                "resume": resume,
                "stop_conditions": _stop_conditions(),
                "message": "Existing claimed goal should be resumed.",
            },
            exit_code=0,
        )

    loop_path_result = _current_loop_path(campaign_path)
    if loop_path_result.exit_code != 0:
        return CampaignRunResult(
            payload={
                **_base_payload(
                    driver=driver,
                    supervised=supervised,
                    campaign_id=campaign_id,
                ),
                "ok": False,
                "status": status_result.payload,
                "error": loop_path_result.payload["error"],
                "stop_conditions": _stop_conditions(),
            },
            exit_code=loop_path_result.exit_code,
        )

    next_result = loop_next(
        loop_path_result.payload["loop_path"],
        claim=True,
        emit_format="codex",
        agent=agent,
        lease=lease,
        event_log=event_log,
    )
    ok = next_result.exit_code == 0
    payload = {
        **_base_payload(
            driver=driver,
            supervised=supervised,
            campaign_id=campaign_id,
        ),
        "ok": ok,
        "status": status_result.payload,
        "next": next_result.payload,
        "resume": status_result.payload.get("resume"),
        "stop_conditions": _stop_conditions(),
        "message": (
            "Supervised campaign step prepared."
            if ok
            else "Supervised campaign step could not prepare a ready goal."
        ),
    }
    if ok and campaign_id is not None:
        append_result = append_campaign_handoff_event(
            event_log=campaign_event_log,
            campaign_id=campaign_id,
            campaign_path=campaign_path,
            loop_id=str(next_result.payload["loop_id"]),
            node_id=str(next_result.payload["node_id"]),
            goal_id=str(next_result.payload["goal_id"]),
            goal_path=str(next_result.payload["goal_path"]),
            agent=agent,
            lease=next_result.payload.get("lease")
            if isinstance(next_result.payload.get("lease"), dict)
            else None,
        )
        payload["campaign_event_log"] = append_result.path
        payload["campaign_event"] = append_result.event
    return CampaignRunResult(payload=payload, exit_code=next_result.exit_code)


def _current_loop_path(campaign_path: Path) -> CampaignCommandResult:
    try:
        raw = campaign_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.run",
                "error": {
                    "code": "campaign_manifest_unreadable",
                    "path": "$.campaign",
                    "message": f"Campaign manifest could not be read: {exc}",
                },
            },
            exit_code=2,
        )

    if not isinstance(payload, dict):
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.run",
                "error": {
                    "code": "campaign_manifest_not_object",
                    "path": "$",
                    "message": "Campaign manifest must be a JSON object.",
                },
            },
            exit_code=2,
        )

    state = payload.get("state")
    artifacts = payload.get("artifacts")
    current_loop = state.get("current_loop") if isinstance(state, dict) else None
    loop_paths = artifacts.get("loops") if isinstance(artifacts, dict) else None
    if not isinstance(current_loop, str) or not isinstance(loop_paths, list):
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.run",
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
                    "command": "campaign.run",
                    "loop_path": loop_path,
                },
                exit_code=0,
            )

    return CampaignCommandResult(
        payload={
            "ok": False,
            "command": "campaign.run",
            "error": {
                "code": "current_loop_unresolved",
                "path": "$.state.current_loop",
                "message": "Campaign current loop does not match a readable declared loop.",
            },
        },
        exit_code=1,
    )


def _base_payload(
    *,
    driver: str,
    supervised: bool,
    campaign_id: str | None,
) -> dict[str, Any]:
    return {
        "command": "campaign.run",
        "mode": "supervised_once",
        "driver": driver,
        "campaign_id": campaign_id,
        "supervised": supervised,
        "autonomous": False,
        "launched": False,
    }


def _usage_error(
    *,
    driver: str,
    supervised: bool,
    code: str,
    path: str,
    message: str,
) -> CampaignRunResult:
    return CampaignRunResult(
        payload={
            **_base_payload(driver=driver, supervised=supervised, campaign_id=None),
            "ok": False,
            "error": {
                "code": code,
                "path": path,
                "message": message,
            },
            "stop_conditions": _stop_conditions(),
        },
        exit_code=2,
    )


def _campaign_id_from_status(payload: dict[str, Any]) -> str | None:
    campaign_id = payload.get("campaign_id")
    if isinstance(campaign_id, str):
        return campaign_id
    lint = payload.get("lint")
    if isinstance(lint, dict):
        lint_campaign_id = lint.get("campaign_id")
        if isinstance(lint_campaign_id, str):
            return lint_campaign_id
    return None


def _resume_from_status(payload: dict[str, Any]) -> dict[str, Any] | None:
    resume = payload.get("resume")
    return resume if isinstance(resume, dict) else None


def _stop_conditions() -> list[str]:
    return [
        "Stop after this single claimed handoff; invoke dp again for the next goal.",
        "Start the claimed goal with the emitted dp goal start command before editing.",
        "Run evidence through dp evidence run or the declared evidence surface separately.",
        "Verify through dp goal verify only after evidence exists and passes.",
        "Block or release through dp if a required decision, spec, validator, "
        "or safe path is missing.",
        "Never claim completion from agent narration; completion requires recorded evidence.",
    ]
