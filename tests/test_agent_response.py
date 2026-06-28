from __future__ import annotations

from dp.core.agent_response import (
    affordances,
    agent_response,
    envelope_legacy_payload,
    next_action,
)


def test_agent_response_has_required_contract_fields() -> None:
    payload = agent_response(
        command="dp agent bootstrap",
        status="ok",
        exit_code=0,
        summary="One sentence.",
        result={"repo": {"root": "."}},
        affordance_payload=affordances(
            phase="orient",
            mutability="read_only",
            idempotent=True,
            safety="safe_orientation",
        ),
        next_actions=[
            next_action("audit", "dp instructions audit --json", "Respect instructions.")
        ],
    )

    assert payload["schema_version"] == "dp.response.v1"
    assert payload["affordances"]["phase"] == "orient"
    assert payload["next_actions"][0]["command"] == "dp instructions audit --json"
    assert set(payload) == {
        "schema_version",
        "command",
        "status",
        "exit_code",
        "summary",
        "result",
        "affordances",
        "next_actions",
        "hints",
        "artifacts",
        "expansions",
    }


def test_envelope_detail_modes_keep_brief_compact_and_full_expandable() -> None:
    legacy = {"ok": True, "command": "goal.status", "goal_id": "GOAL-1", "events": [1, 2, 3]}

    brief = envelope_legacy_payload(
        command="dp goal status goal.json",
        payload=legacy,
        exit_code=0,
        detail="brief",
        phase="work",
        mutability="read_only",
        idempotent=True,
        safety="safe_goal_state_read",
        summary="Goal is ready.",
    )
    full = envelope_legacy_payload(
        command="dp goal status goal.json",
        payload=legacy,
        exit_code=0,
        detail="full",
        phase="work",
        mutability="read_only",
        idempotent=True,
        safety="safe_goal_state_read",
        summary="Goal is ready.",
    )

    assert brief["result"] == {}
    assert full["result"]["payload"]["events"] == [1, 2, 3]
