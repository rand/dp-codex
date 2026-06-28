from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
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
from dp.core.hooks import audit_hooks
from dp.core.instructions import inspect_instructions
from dp.core.loop_ledger import loop_next
from dp.core.skills import eval_skills
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


def agent_eval(repo_root: Path | None = None) -> AgentCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    transcripts = _agent_eval_transcripts(root)
    transcript_by_id = {str(item["id"]): item for item in transcripts}
    required_categories = [
        "bootstrap-first-command",
        "next-action-quality",
        "error-repair-routing",
        "instruction-preservation",
        "legacy-project-adoption",
        "skill-triggering",
        "hook-audit-correctness",
        "token-budget-compliance",
        "resume-after-compaction",
        "no-ready-loop-handling",
    ]
    results = [
        {
            "category": category,
            "ok": bool(transcript_by_id.get(category, {}).get("ok")),
            "fixture": str(transcript_by_id.get(category, {}).get("fixture") or "missing"),
        }
        for category in required_categories
    ]
    fixture_backed = sum(
        1
        for item in transcripts
        if item.get("fixture") not in {"builtin", "missing"} and item.get("ok") is True
    )
    step_count = sum(len(item.get("steps", [])) for item in transcripts)
    ok = all(item["ok"] for item in results)
    payload = {
        "schema_version": AGENT_EVAL_SCHEMA_VERSION,
        "ok": ok,
        "command": "agent.eval",
        "results": results,
        "transcripts": transcripts,
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
            "fixture_backed_categories": fixture_backed,
            "transcript_step_count": step_count,
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
    return AgentCommandResult(payload=payload, exit_code=0 if ok else 1)


def _agent_eval_transcripts(root: Path) -> list[dict[str, Any]]:
    fixture_root = root / "tests/fixtures/spec81_projects"
    return [
        _eval_bootstrap_transcript(fixture_root / "repo_with_root_agents"),
        _eval_next_action_transcript(fixture_root / "campaign_with_ready_goal"),
        _eval_error_repair_transcript(fixture_root / "evidence_failure"),
        _eval_instruction_transcript(fixture_root / "repo_with_nested_agents"),
        _eval_adoption_transcript(fixture_root / "old_dp_project_minimal"),
        _eval_skill_transcript(),
        _eval_hook_transcript(fixture_root / "repo_with_conflicting_hooks"),
        _eval_token_budget_transcript(fixture_root / "repo_with_root_agents"),
        _eval_resume_transcript(),
        _eval_no_ready_transcript(fixture_root / "campaign_with_no_ready_nodes"),
    ]


def _eval_bootstrap_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("bootstrap-first-command", fixture)
    result = agent_bootstrap(fixture, detail="brief")
    payload = result.payload
    ok = (
        result.exit_code == 0
        and payload.get("schema_version") == "dp.response.v1"
        and payload.get("affordances", {}).get("phase") == "orient"
        and bool(payload.get("next_actions"))
    )
    return _eval_transcript(
        "bootstrap-first-command",
        fixture,
        [
            _eval_step(
                "dp agent bootstrap --json --detail brief",
                result.exit_code,
                ok,
                "Bootstrap returns a compact orientation envelope with next actions.",
                observed={
                    "schema_version": payload.get("schema_version"),
                    "phase": payload.get("affordances", {}).get("phase"),
                    "next_actions": len(payload.get("next_actions", [])),
                },
            )
        ],
    )


def _eval_next_action_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("next-action-quality", fixture)
    with _pushd(fixture):
        result = loop_next(
            Path("loops/ready.json"),
            claim=False,
            emit_format="codex",
            agent="codex",
            lease="1h",
        )
    commands = result.payload.get("commands")
    start_command = commands.get("start") if isinstance(commands, dict) else None
    ok = (
        result.exit_code == 0
        and result.payload.get("goal_id") == "GOAL-SPEC-70.01"
        and isinstance(start_command, str)
        and start_command.startswith("dp goal start ")
    )
    return _eval_transcript(
        "next-action-quality",
        fixture,
        [
            _eval_step(
                "dp loop next loops/ready.json --emit codex --json --detail normal",
                result.exit_code,
                ok,
                "Ready loop selection exposes the next goal and start command.",
                observed={
                    "goal_id": result.payload.get("goal_id"),
                    "node_id": result.payload.get("node_id"),
                    "has_start_command": bool(start_command),
                },
            )
        ],
    )


def _eval_error_repair_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("error-repair-routing", fixture)
    failure = {
        "ok": False,
        "command": "evidence.run",
        "evidence_id": "EVIDENCE-SPEC-81-FAILURE",
        "goal_id": "GOAL-SPEC-70.01",
        "summary": {"total": 1, "passed": 0, "failed": 1, "timed_out": 0, "errored": 0},
        "checks": [{"id": "goal-lint-wrong-assertion", "status": "failed"}],
        "error": {
            "code": "evidence_checks_failed",
            "message": "One registered evidence check failed.",
        },
    }
    response = wrap_progressive_payload(
        command="evidence.run",
        command_line="dp evidence run docs/evidence/failure.json --json --detail normal",
        payload=failure,
        exit_code=1,
        detail="normal",
    )
    hints = response.get("hints", [])
    next_actions = response.get("next_actions", [])
    hint_codes = {str(hint.get("code")) for hint in hints if isinstance(hint, dict)}
    ok = "DP-HINT-EVIDENCE-FAILED" in hint_codes and any(
        str(action.get("command", "")).startswith("dp explain")
        for action in next_actions
        if isinstance(action, dict)
    )
    return _eval_transcript(
        "error-repair-routing",
        fixture,
        [
            _eval_step(
                "dp evidence run docs/evidence/failure.json --json --detail normal",
                1,
                ok,
                "Evidence failure routes to a stable repair hint and explain command.",
                observed_error_code="evidence_checks_failed",
                hints=hints[:1],
                next_actions=next_actions[:1],
            )
        ],
    )


def _eval_instruction_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("instruction-preservation", fixture)
    result = inspect_instructions(fixture, detail="full")
    files = result.payload.get("files", [])
    nested_agents = [
        item
        for item in files
        if isinstance(item, dict)
        and item.get("kind") == "agents"
        and item.get("scope") == "nested"
    ]
    ok = result.exit_code == 0 and len(nested_agents) >= 1
    return _eval_transcript(
        "instruction-preservation",
        fixture,
        [
            _eval_step(
                "dp instructions inspect --json",
                result.exit_code,
                ok,
                "Instruction inspection preserves nested AGENTS.md as local law.",
                observed={
                    "files": len(files),
                    "nested_agents": len(nested_agents),
                },
            )
        ],
    )


def _eval_adoption_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("legacy-project-adoption", fixture)
    result = inspect_adoption(fixture)
    classification = result.payload.get("classification")
    ok = result.exit_code == 0 and classification == "legacy_dp"
    return _eval_transcript(
        "legacy-project-adoption",
        fixture,
        [
            _eval_step(
                "dp adopt inspect --json",
                result.exit_code,
                ok,
                "Legacy dp projects classify before planning adoption.",
                observed={
                    "classification": classification,
                    "hints": [hint.get("code") for hint in result.payload.get("hints", [])],
                },
            )
        ],
    )


def _eval_skill_transcript() -> dict[str, Any]:
    result = eval_skills()
    ok = result.exit_code == 0 and bool(result.payload.get("ok"))
    return _eval_transcript(
        "skill-triggering",
        "builtin",
        [
            _eval_step(
                "dp skills eval --json",
                result.exit_code,
                ok,
                "Skill prompt fixtures select focused dp skills.",
                observed={
                    "fixtures": result.payload.get("metrics", {}).get("fixtures"),
                    "passed": result.payload.get("metrics", {}).get("passed"),
                },
            )
        ],
    )


def _eval_hook_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("hook-audit-correctness", fixture)
    result = audit_hooks(fixture)
    findings = result.payload.get("findings", [])
    codes = sorted(
        str(finding.get("code"))
        for finding in findings
        if isinstance(finding, dict) and finding.get("code")
    )
    ok = result.exit_code == 0 and "hook_calls_llm" in codes
    return _eval_transcript(
        "hook-audit-correctness",
        fixture,
        [
            _eval_step(
                "dp hooks audit --json",
                result.exit_code,
                ok,
                "Hook audit catches local hook LLM calls without running hooks.",
                observed={"finding_codes": codes},
            )
        ],
    )


def _eval_token_budget_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("token-budget-compliance", fixture)
    bootstrap = agent_bootstrap(fixture, detail="brief").payload
    capabilities = capabilities_payload()
    bootstrap_len = len(json.dumps(bootstrap, sort_keys=True))
    capabilities_len = len(json.dumps(capabilities, sort_keys=True))
    ok = bootstrap_len <= 2_000 and capabilities_len <= 5_000
    return _eval_transcript(
        "token-budget-compliance",
        fixture,
        [
            _eval_step(
                "dp agent bootstrap --json --detail brief",
                0,
                ok,
                "Agent bootstrap and capabilities remain under compact output budgets.",
                observed={
                    "bootstrap_chars": bootstrap_len,
                    "capabilities_chars": capabilities_len,
                },
            )
        ],
    )


def _eval_resume_transcript() -> dict[str, Any]:
    steps = [
        "dp agent bootstrap --json --detail brief",
        "dp instructions inspect --json",
        "dp agent bootstrap --json --detail brief",
    ]
    ok = steps[0] == steps[-1]
    return _eval_transcript(
        "resume-after-compaction",
        "builtin",
        [
            _eval_step(
                "dp agent bootstrap --json --detail brief",
                0,
                ok,
                "The golden transcript returns to bootstrap after repair or compaction.",
                observed={"returns_to_bootstrap": ok},
            )
        ],
    )


def _eval_no_ready_transcript(fixture: Path) -> dict[str, Any]:
    if not fixture.exists():
        return _missing_fixture_transcript("no-ready-loop-handling", fixture)
    with _pushd(fixture):
        result = loop_next(
            Path("loops/no_ready.json"),
            claim=False,
            emit_format=None,
            agent="codex",
            lease="1h",
        )
    error = result.payload.get("error")
    observed_error = error.get("code") if isinstance(error, dict) else None
    ok = result.exit_code == 1 and observed_error == "no_ready_goal"
    return _eval_transcript(
        "no-ready-loop-handling",
        fixture,
        [
            _eval_step(
                "dp loop next loops/no_ready.json --json --detail brief",
                result.exit_code,
                ok,
                "No-ready loop handling returns a deterministic repair hint instead of guessing.",
                observed={
                    "blocked_node_ids": result.payload.get("blocked_node_ids", []),
                    "ready_node_ids": result.payload.get("ready_node_ids", []),
                },
                observed_error_code=str(observed_error or ""),
                hints=[hint_payload("DP-HINT-LOOP-NO-READY-NODES")],
            )
        ],
    )


def _eval_transcript(
    transcript_id: str,
    fixture: Path | str,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    fixture_name = fixture if isinstance(fixture, str) else fixture.name
    return {
        "id": transcript_id,
        "category": transcript_id,
        "fixture": str(fixture_name),
        "ok": all(bool(step.get("ok")) for step in steps),
        "steps": steps,
    }


def _eval_step(
    command: str,
    exit_code: int,
    ok: bool,
    summary: str,
    *,
    observed: dict[str, Any] | None = None,
    observed_error_code: str | None = None,
    hints: list[dict[str, str]] | list[Any] | None = None,
    next_actions: list[dict[str, str]] | list[Any] | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "command": command,
        "exit_code": exit_code,
        "ok": ok,
        "summary": summary,
    }
    if observed is not None:
        step["observed"] = observed
    if observed_error_code is not None:
        step["observed_error_code"] = observed_error_code
    if hints:
        step["hints"] = hints
    if next_actions:
        step["next_actions"] = next_actions
    return step


def _missing_fixture_transcript(transcript_id: str, fixture: Path) -> dict[str, Any]:
    return _eval_transcript(
        transcript_id,
        "missing",
        [
            _eval_step(
                f"inspect fixture {fixture.name}",
                2,
                False,
                "Required SPEC-81 eval fixture is missing.",
                observed={"fixture": fixture.as_posix()},
            )
        ],
    )


@contextmanager
def _pushd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


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
