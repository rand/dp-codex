from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from dp.core.campaign_events import DEFAULT_CAMPAIGN_EVENT_LOG, campaign_event_summary
from dp.core.evidence_artifacts import default_evidence_run_path, evidence_artifact_commands
from dp.core.evidence_lint import lint_evidence_file
from dp.core.goal_emit import emit_goal_prompt
from dp.core.goal_lint import lint_goal_file
from dp.core.goal_state import DEFAULT_GOAL_EVENT_LOG
from dp.core.loop_ledger import lint_loop_file, loop_status

# @trace SPEC-80.06
SUPPORTED_CAMPAIGN_SCHEMA_VERSION = "0.1"
CAMPAIGN_ID_PATTERN = re.compile(r"^CAMPAIGN-[A-Za-z0-9][A-Za-z0-9_.-]*$")
GOAL_ID_PATTERN = re.compile(r"^GOAL-[A-Za-z0-9][A-Za-z0-9_.-]*$")
CAMPAIGN_STATUSES = frozenset(
    {"draft", "ready", "active", "blocked", "verified", "abandoned"}
)
PATH_ARTIFACT_FIELDS = (
    "specs",
    "adrs",
    "goals",
    "evidence_plans",
    "loops",
)
REQUIRED_PATH_ARTIFACT_FIELDS = frozenset({"goals", "loops"})
BEADS_ARTIFACT_FIELDS = ("beads_epics", "beads_issues")


@dataclass(frozen=True)
class CampaignLintFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class CampaignLintReport:
    valid: bool
    campaign_id: str | None
    errors: tuple[CampaignLintFinding, ...]
    warnings: tuple[CampaignLintFinding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "campaign_id": self.campaign_id,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass(frozen=True)
class CampaignLintResult:
    report: CampaignLintReport
    exit_code: int


@dataclass(frozen=True)
class CampaignCommandResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class CampaignContract:
    campaign_id: str
    title: str
    primary_spec_path: str
    artifact_paths: dict[str, tuple[str, ...]]
    loop_ids: dict[str, str]
    goal_ids: dict[str, str]
    state: dict[str, Any]


@dataclass(frozen=True)
class CampaignValidation:
    contract: CampaignContract | None
    result: CampaignLintResult


def lint_campaign_file(path: Path) -> CampaignLintResult:
    return _validate_campaign_file(path).result


def campaign_status(
    campaign_path: Path,
    *,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
    campaign_event_log: Path = DEFAULT_CAMPAIGN_EVENT_LOG,
) -> CampaignCommandResult:
    validation = _validate_campaign_file(campaign_path)
    if validation.result.exit_code != 0 or validation.contract is None:
        return _lint_failure_payload("campaign.status", validation.result)

    contract = validation.contract
    current_loop_id = str(contract.state["current_loop"])
    current_loop_path = Path(contract.loop_ids[current_loop_id])
    loop_result = loop_status(current_loop_path, event_log=event_log)
    if loop_result.exit_code != 0:
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.status",
                "campaign_id": contract.campaign_id,
                "error": {
                    "code": "loop_status_failed",
                    "message": "Current loop status could not be reconstructed.",
                },
                "loop": loop_result.payload,
            },
            exit_code=loop_result.exit_code,
        )

    summary = _campaign_summary(contract, loop_result.payload)
    events = campaign_event_summary(
        campaign_id=contract.campaign_id,
        event_log=campaign_event_log,
    )
    resume = _resume_handoff(
        contract=contract,
        campaign_path=campaign_path,
        loop_payload=loop_result.payload,
    )
    payload = {
        "ok": True,
        "command": "campaign.status",
        "campaign_id": contract.campaign_id,
        "title": contract.title,
        "manifest_state": contract.state,
        "derived_status": _derive_campaign_status(loop_result.payload),
        "primary_spec": {
            "path": contract.primary_spec_path,
            "exists": Path(contract.primary_spec_path).exists(),
        },
        "artifacts": _artifact_summary(contract),
        "loop": loop_result.payload,
        "events": events,
        "resume": resume,
        "summary": summary,
    }
    return CampaignCommandResult(payload=payload, exit_code=0)


def campaign_recover(
    campaign_path: Path,
    *,
    event_log: Path = DEFAULT_GOAL_EVENT_LOG,
    campaign_event_log: Path = DEFAULT_CAMPAIGN_EVENT_LOG,
) -> CampaignCommandResult:
    validation = _validate_campaign_file(campaign_path)
    missing_artifacts = _missing_artifacts(validation.result.report)
    if validation.result.exit_code != 0 or validation.contract is None:
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.recover",
                "campaign_id": validation.result.report.campaign_id,
                "recoverable": False,
                "lint": validation.result.report.to_dict(),
                "missing_artifacts": missing_artifacts,
            },
            exit_code=validation.result.exit_code,
        )

    status_result = campaign_status(
        campaign_path,
        event_log=event_log,
        campaign_event_log=campaign_event_log,
    )
    if status_result.exit_code != 0:
        return CampaignCommandResult(
            payload={
                "ok": False,
                "command": "campaign.recover",
                "campaign_id": validation.contract.campaign_id,
                "recoverable": False,
                "lint": validation.result.report.to_dict(),
                "missing_artifacts": missing_artifacts,
                "status": status_result.payload,
            },
            exit_code=status_result.exit_code,
        )

    return CampaignCommandResult(
        payload={
            "ok": True,
            "command": "campaign.recover",
            "campaign_id": validation.contract.campaign_id,
            "recoverable": True,
            "lint": validation.result.report.to_dict(),
            "missing_artifacts": missing_artifacts,
            "status": status_result.payload,
            "events": status_result.payload.get("events"),
            "resume": status_result.payload.get("resume"),
        },
        exit_code=0,
    )


def _validate_campaign_file(path: Path) -> CampaignValidation:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        result = _input_error(
            code="missing_file",
            path="$",
            message=f"Campaign manifest file not found: {path.as_posix()}",
        )
        return CampaignValidation(contract=None, result=result)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        result = _input_error(
            code="malformed_json",
            path="$",
            message=f"Campaign manifest is not valid JSON: line {exc.lineno} column {exc.colno}.",
        )
        return CampaignValidation(contract=None, result=result)

    return _validate_campaign_payload(payload)


def _validate_campaign_payload(payload: Any) -> CampaignValidation:
    if not isinstance(payload, dict):
        return CampaignValidation(
            contract=None,
            result=_input_error(
                code="json_object_required",
                path="$",
                message="Campaign manifest must be a JSON object.",
            ),
        )

    campaign_id = _non_empty_string(payload.get("id"))
    schema_version = _non_empty_string(payload.get("schema_version"))
    if schema_version != SUPPORTED_CAMPAIGN_SCHEMA_VERSION:
        value = schema_version if schema_version is not None else "<missing>"
        return CampaignValidation(
            contract=None,
            result=_input_error(
                code="unsupported_schema",
                path="$.schema_version",
                message=(
                    f"Unsupported campaign schema version {value}. "
                    f"Expected {SUPPORTED_CAMPAIGN_SCHEMA_VERSION}."
                ),
                campaign_id=campaign_id,
            ),
        )

    errors: list[CampaignLintFinding] = []
    warnings: list[CampaignLintFinding] = []
    title = _non_empty_string(payload.get("title"))

    if campaign_id is None:
        errors.append(
            _finding("missing_id", "$.id", "Campaign manifest must define an id.")
        )
    elif CAMPAIGN_ID_PATTERN.fullmatch(campaign_id) is None:
        errors.append(
            _finding(
                "invalid_id",
                "$.id",
                "Campaign manifest id must look like CAMPAIGN-name.",
            )
        )

    if title is None:
        errors.append(
            _finding("missing_title", "$.title", "Campaign manifest must define a title.")
        )

    primary_spec_path = _validate_primary_spec(payload.get("primary_spec"), errors)
    artifact_paths, loop_ids, goal_ids = _validate_artifacts(payload.get("artifacts"), errors)
    _validate_loop_closure(artifact_paths, errors)
    state = _validate_state(payload.get("state"), loop_ids, goal_ids, errors)

    contract: CampaignContract | None = None
    if (
        not errors
        and campaign_id is not None
        and title is not None
        and primary_spec_path is not None
        and state is not None
    ):
        contract = CampaignContract(
            campaign_id=campaign_id,
            title=title,
            primary_spec_path=primary_spec_path,
            artifact_paths=artifact_paths,
            loop_ids=loop_ids,
            goal_ids=goal_ids,
            state=state,
        )

    return CampaignValidation(
        contract=contract,
        result=CampaignLintResult(
            report=CampaignLintReport(
                valid=not errors,
                campaign_id=campaign_id,
                errors=tuple(errors),
                warnings=tuple(warnings),
            ),
            exit_code=0 if not errors else 1,
        ),
    )


def _validate_primary_spec(
    primary_spec: Any,
    errors: list[CampaignLintFinding],
) -> str | None:
    if not isinstance(primary_spec, dict):
        errors.append(
            _finding(
                "missing_primary_spec",
                "$.primary_spec",
                "Campaign manifest must define primary_spec.",
            )
        )
        return None

    path_value = _non_empty_string(primary_spec.get("path"))
    if path_value is None:
        errors.append(
            _finding(
                "missing_primary_spec_path",
                "$.primary_spec.path",
                "Campaign primary_spec must define path.",
            )
        )
        return None
    if not _is_sane_relative_path(path_value):
        errors.append(
            _finding(
                "invalid_primary_spec_path",
                "$.primary_spec.path",
                "Campaign primary_spec.path must be a sane relative path.",
            )
        )
        return None
    if not Path(path_value).exists():
        errors.append(
            _finding(
                "missing_artifact",
                "$.primary_spec.path",
                f"Declared campaign artifact does not exist: {path_value}.",
            )
        )
    return path_value


def _validate_artifacts(
    artifacts: Any,
    errors: list[CampaignLintFinding],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str], dict[str, str]]:
    artifact_paths: dict[str, tuple[str, ...]] = {field: () for field in PATH_ARTIFACT_FIELDS}
    loop_ids: dict[str, str] = {}
    goal_ids: dict[str, str] = {}

    if not isinstance(artifacts, dict):
        errors.append(
            _finding(
                "missing_artifacts",
                "$.artifacts",
                "Campaign manifest must define artifacts.",
            )
        )
        return artifact_paths, loop_ids, goal_ids

    seen_paths: dict[str, str] = {}
    for field in PATH_ARTIFACT_FIELDS:
        value = artifacts.get(field, [])
        path = f"$.artifacts.{field}"
        if field in REQUIRED_PATH_ARTIFACT_FIELDS and (not isinstance(value, list) or not value):
            errors.append(
                _finding(
                    f"missing_{field}",
                    path,
                    f"Campaign manifest must declare at least one {field} artifact.",
                )
            )
            continue
        if not isinstance(value, list):
            errors.append(
                _finding(
                    "invalid_artifact_list",
                    path,
                    f"Campaign artifact field {field} must be an array of paths.",
                )
            )
            continue

        values: list[str] = []
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            artifact_path = _non_empty_string(item)
            if artifact_path is None:
                errors.append(
                    _finding(
                        "invalid_artifact_path",
                        item_path,
                        "Campaign artifact paths must be non-empty strings.",
                    )
                )
                continue
            if not _is_sane_relative_path(artifact_path):
                errors.append(
                    _finding(
                        "invalid_artifact_path",
                        item_path,
                        "Campaign artifact path must be a sane relative path.",
                    )
                )
                continue
            if artifact_path in seen_paths:
                errors.append(
                    _finding(
                        "duplicate_artifact",
                        item_path,
                        f"Campaign artifact path duplicates {seen_paths[artifact_path]}.",
                    )
                )
            else:
                seen_paths[artifact_path] = item_path

            values.append(artifact_path)
            _validate_artifact_file(field, artifact_path, item_path, errors, loop_ids, goal_ids)

        artifact_paths[field] = tuple(values)

    for field in BEADS_ARTIFACT_FIELDS:
        _validate_optional_string_list(artifacts.get(field, []), f"$.artifacts.{field}", errors)

    return artifact_paths, loop_ids, goal_ids


def _validate_artifact_file(
    field: str,
    artifact_path: str,
    json_path: str,
    errors: list[CampaignLintFinding],
    loop_ids: dict[str, str],
    goal_ids: dict[str, str],
) -> None:
    path = Path(artifact_path)
    if not path.exists():
        errors.append(
            _finding(
                "missing_artifact",
                json_path,
                f"Declared campaign artifact does not exist: {artifact_path}.",
            )
        )
        return

    if field == "goals":
        goal_result = lint_goal_file(path)
        if goal_result.exit_code != 0:
            errors.append(
                _finding(
                    "invalid_goal_contract",
                    json_path,
                    "Campaign goal artifact must reference a valid GoalContract.",
                )
            )
        elif goal_result.report.goal_id is not None:
            goal_ids[goal_result.report.goal_id] = artifact_path
    elif field == "evidence_plans":
        evidence_result = lint_evidence_file(path)
        if evidence_result.exit_code != 0:
            errors.append(
                _finding(
                    "invalid_evidence_plan",
                    json_path,
                    "Campaign evidence artifact must reference a valid EvidencePlan.",
                )
            )
    elif field == "loops":
        loop_result = lint_loop_file(path)
        if loop_result.exit_code != 0:
            errors.append(
                _finding(
                    "invalid_loop_ledger",
                    json_path,
                    "Campaign loop artifact must reference a valid LoopLedger.",
                )
            )
        elif loop_result.report.loop_id is not None:
            loop_ids[loop_result.report.loop_id] = artifact_path


def _validate_loop_closure(
    artifact_paths: dict[str, tuple[str, ...]],
    errors: list[CampaignLintFinding],
) -> None:
    goal_paths = set(artifact_paths["goals"])
    evidence_paths = set(artifact_paths["evidence_plans"])
    for loop_index, loop_path in enumerate(artifact_paths["loops"]):
        path = Path(loop_path)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        nodes = payload.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node_index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            node_path = f"$.artifacts.loops[{loop_index}].nodes[{node_index}]"
            goal_path = _non_empty_string(node.get("goal_path"))
            if goal_path is not None and goal_path not in goal_paths:
                errors.append(
                    _finding(
                        "loop_goal_not_declared",
                        f"{node_path}.goal_path",
                        "Loop node goal_path must be declared in artifacts.goals.",
                    )
                )
            evidence_plan = _non_empty_string(node.get("evidence_plan"))
            if evidence_plan is not None and evidence_plan not in evidence_paths:
                errors.append(
                    _finding(
                        "loop_evidence_not_declared",
                        f"{node_path}.evidence_plan",
                        "Loop node evidence_plan must be declared in artifacts.evidence_plans.",
                    )
                )


def _validate_state(
    state: Any,
    loop_ids: dict[str, str],
    goal_ids: dict[str, str],
    errors: list[CampaignLintFinding],
) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        errors.append(
            _finding("missing_state", "$.state", "Campaign manifest must define state.")
        )
        return None

    status = _non_empty_string(state.get("status"))
    current_loop = _non_empty_string(state.get("current_loop"))
    current_goal_value = state.get("current_goal")

    if status not in CAMPAIGN_STATUSES:
        errors.append(
            _finding(
                "invalid_status",
                "$.state.status",
                "Campaign state.status must be one of: abandoned, active, blocked, "
                "draft, ready, verified.",
            )
        )
    if current_loop is None:
        errors.append(
            _finding(
                "missing_current_loop",
                "$.state.current_loop",
                "Campaign state.current_loop must reference a declared loop id.",
            )
        )
    elif current_loop not in loop_ids:
        errors.append(
            _finding(
                "unknown_current_loop",
                "$.state.current_loop",
                "Campaign state.current_loop must match a declared loop id.",
            )
        )

    current_goal: str | None = None
    if current_goal_value is not None:
        current_goal = _non_empty_string(current_goal_value)
        if current_goal is None or GOAL_ID_PATTERN.fullmatch(current_goal) is None:
            errors.append(
                _finding(
                    "invalid_current_goal",
                    "$.state.current_goal",
                    "Campaign state.current_goal must be null or look like GOAL-name.",
                )
            )
        elif goal_ids and current_goal not in goal_ids:
            errors.append(
                _finding(
                    "unknown_current_goal",
                    "$.state.current_goal",
                    "Campaign state.current_goal must match a declared GoalContract id.",
                )
            )

    if status is None or current_loop is None:
        return None
    return {"status": status, "current_loop": current_loop, "current_goal": current_goal}


def _campaign_summary(
    contract: CampaignContract,
    loop_payload: dict[str, Any],
) -> dict[str, Any]:
    nodes = _loop_nodes(loop_payload)
    state_counts = _state_counts(nodes)
    return {
        "specs": len(contract.artifact_paths["specs"]),
        "adrs": len(contract.artifact_paths["adrs"]),
        "goals": len(contract.artifact_paths["goals"]),
        "evidence_plans": len(contract.artifact_paths["evidence_plans"]),
        "loops": len(contract.artifact_paths["loops"]),
        "ready_goals": state_counts.get("ready", 0),
        "waiting_goals": state_counts.get("waiting", 0),
        "blocked_goals": state_counts.get("blocked", 0),
        "active_goals": sum(
            state_counts.get(state, 0) for state in ("claimed", "started", "pursuing")
        ),
        "evidence_pending_goals": state_counts.get("evidence_pending", 0),
        "verified_goals": state_counts.get("verified", 0),
    }


def _derive_campaign_status(loop_payload: dict[str, Any]) -> str:
    nodes = _loop_nodes(loop_payload)
    if not nodes:
        return "draft"
    states = [_node_state(node) for node in nodes]
    if states and all(state == "verified" for state in states):
        return "verified"
    if any(state == "blocked" for state in states):
        return "blocked"
    return "active"


def _artifact_summary(contract: CampaignContract) -> dict[str, Any]:
    return {
        "primary_spec": contract.primary_spec_path,
        "specs": list(contract.artifact_paths["specs"]),
        "adrs": list(contract.artifact_paths["adrs"]),
        "goals": list(contract.artifact_paths["goals"]),
        "evidence_plans": list(contract.artifact_paths["evidence_plans"]),
        "loops": list(contract.artifact_paths["loops"]),
    }


def _resume_handoff(
    *,
    contract: CampaignContract,
    campaign_path: Path,
    loop_payload: dict[str, Any],
) -> dict[str, Any]:
    nodes = _loop_nodes(loop_payload)
    loop_id = _non_empty_string(loop_payload.get("loop_id")) or str(contract.state["current_loop"])
    stale_claims = _stale_claims(nodes)

    for node in nodes:
        if _node_state(node) in {"claimed", "started", "pursuing"}:
            return _node_resume(
                action="resume_claimed_goal",
                reason="A current-loop goal has an active non-stale claim.",
                campaign_id=contract.campaign_id,
                loop_id=loop_id,
                campaign_path=campaign_path,
                node=node,
                stale_claims=stale_claims,
                include_codex_goal=True,
            )

    for node in nodes:
        if _node_state(node) == "evidence_pending":
            evidence = _last_event_text(node, "evidence")
            return _node_resume(
                action="verify_evidence",
                reason="A current-loop goal has recorded evidence pending verification.",
                campaign_id=contract.campaign_id,
                loop_id=loop_id,
                campaign_path=campaign_path,
                node=node,
                stale_claims=stale_claims,
                evidence=evidence,
            )

    for node in nodes:
        if _node_state(node) == "blocked":
            return _node_resume(
                action="resolve_blocker",
                reason="A current-loop goal is blocked and must be resolved before dependent work.",
                campaign_id=contract.campaign_id,
                loop_id=loop_id,
                campaign_path=campaign_path,
                node=node,
                stale_claims=stale_claims,
            )

    for node in nodes:
        if _node_state(node) == "ready":
            return _node_resume(
                action="claim_next_goal",
                reason="A current-loop goal is ready to claim.",
                campaign_id=contract.campaign_id,
                loop_id=loop_id,
                campaign_path=campaign_path,
                node=node,
                stale_claims=stale_claims,
            )

    if nodes and all(_node_state(node) == "verified" for node in nodes):
        return {
            "command": "campaign.resume",
            "action": "campaign_verified",
            "reason": "All current-loop goals are verified.",
            "campaign_id": contract.campaign_id,
            "loop_id": loop_id,
            "stale_claims": stale_claims,
            "commands": {
                "status": f"dp campaign status {campaign_path.as_posix()} --json",
                "recover": f"dp campaign recover {campaign_path.as_posix()} --json",
            },
        }

    return {
        "command": "campaign.resume",
        "action": "no_ready_work",
        "reason": "No current-loop goal is active, blocked, evidence-pending, ready, or verified.",
        "campaign_id": contract.campaign_id,
        "loop_id": loop_id,
        "stale_claims": stale_claims,
        "commands": {
            "status": f"dp campaign status {campaign_path.as_posix()} --json",
            "recover": f"dp campaign recover {campaign_path.as_posix()} --json",
            "campaign_run": (
                f"dp campaign run {campaign_path.as_posix()} --driver codex --supervised --json"
            ),
        },
    }


def _node_resume(
    *,
    action: str,
    reason: str,
    campaign_id: str,
    loop_id: str,
    campaign_path: Path,
    node: dict[str, Any],
    stale_claims: list[dict[str, Any]],
    evidence: str | None = None,
    include_codex_goal: bool = False,
) -> dict[str, Any]:
    goal_path = _node_text(node, "goal_path") or "<goal.json>"
    goal_id = _node_text(node, "goal_id")
    evidence_plan = _node_text(node, "evidence_plan")
    verify_evidence = evidence or default_evidence_run_path(goal_id).as_posix()
    evidence_commands = evidence_artifact_commands(
        goal_path=Path(goal_path),
        goal_id=goal_id,
        evidence_plan=evidence_plan,
    )
    if evidence is not None:
        evidence_commands["complete"] = f"dp goal complete {goal_path} --evidence {evidence} --json"
        evidence_commands["verify"] = f"dp verify --goal {goal_path} --evidence {evidence} --json"
    commands = {
        "status": f"dp goal status {goal_path} --json",
        "start": f"dp goal start {goal_path} --agent codex --json",
        "heartbeat": f"dp goal heartbeat {goal_path} --json",
        **evidence_commands,
        "block": f"dp goal block {goal_path} --reason <reason> --write-artifact --json",
        "release": f"dp goal release {goal_path} --reason <reason> --json",
        "campaign_run": (
            f"dp campaign run {campaign_path.as_posix()} --driver codex --supervised --json"
        ),
    }
    resume: dict[str, Any] = {
        "command": "campaign.resume",
        "action": action,
        "reason": reason,
        "campaign_id": campaign_id,
        "loop_id": loop_id,
        "node_id": _node_text(node, "node_id"),
        "goal_id": goal_id,
        "goal_path": goal_path,
        "beads_issue_id": _node_text(node, "beads_issue_id"),
        "lease": node.get("lease") if isinstance(node.get("lease"), dict) else None,
        "blocked": node.get("blocked") if isinstance(node.get("blocked"), dict) else None,
        "evidence": verify_evidence,
        "evidence_plan": evidence_plan,
        "stale_claims": stale_claims,
        "commands": commands,
    }
    if include_codex_goal:
        codex_goal = _codex_goal(goal_path)
        if codex_goal is not None:
            resume["codex_goal"] = codex_goal
    return resume


def _stale_claims(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for node in nodes:
        lease = node.get("lease")
        if not isinstance(lease, dict) or lease.get("stale") is not True:
            continue
        stale.append(
            {
                "node_id": _node_text(node, "node_id"),
                "goal_id": _node_text(node, "goal_id"),
                "holder": lease.get("holder"),
                "expires_at": lease.get("expires_at"),
            }
        )
    return stale


def _last_event_text(node: dict[str, Any], field: str) -> str | None:
    last_event = node.get("last_event")
    if not isinstance(last_event, dict):
        return None
    return _non_empty_string(last_event.get(field))


def _node_text(node: dict[str, Any], field: str) -> str | None:
    return _non_empty_string(node.get(field))


def _codex_goal(goal_path: str) -> str | None:
    emit_result = emit_goal_prompt(Path(goal_path), output_format="codex")
    if emit_result.exit_code != 0:
        return None
    codex_goal = emit_result.payload.get("codex_goal")
    return codex_goal if isinstance(codex_goal, str) else None


def _loop_nodes(loop_payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = loop_payload.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [node for node in nodes if isinstance(node, dict)]


def _state_counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        state = _node_state(node)
        counts[state] = counts.get(state, 0) + 1
    return counts


def _node_state(node: dict[str, Any]) -> str:
    value = node.get("state")
    return value if isinstance(value, str) else "unknown"


def _missing_artifacts(report: CampaignLintReport) -> list[str]:
    missing: list[str] = []
    prefix = "Declared campaign artifact does not exist: "
    for error in report.errors:
        if error.code != "missing_artifact" or not error.message.startswith(prefix):
            continue
        value = error.message[len(prefix) :]
        missing.append(value.removesuffix("."))
    return missing


def _lint_failure_payload(command: str, result: CampaignLintResult) -> CampaignCommandResult:
    return CampaignCommandResult(
        payload={
            "ok": False,
            "command": command,
            "lint": result.report.to_dict(),
        },
        exit_code=result.exit_code,
    )


def _input_error(
    *,
    code: str,
    path: str,
    message: str,
    campaign_id: str | None = None,
) -> CampaignLintResult:
    return CampaignLintResult(
        report=CampaignLintReport(
            valid=False,
            campaign_id=campaign_id,
            errors=(_finding(code, path, message),),
        ),
        exit_code=2,
    )


def _validate_optional_string_list(
    value: Any,
    path: str,
    errors: list[CampaignLintFinding],
) -> None:
    if not isinstance(value, list):
        errors.append(
            _finding(
                "invalid_artifact_list",
                path,
                "Campaign Beads artifact fields must be arrays of non-empty strings.",
            )
        )
        return
    for index, item in enumerate(value):
        if _non_empty_string(item) is None:
            errors.append(
                _finding(
                    "invalid_artifact_ref",
                    f"{path}[{index}]",
                    "Campaign Beads artifact refs must be non-empty strings.",
                )
            )


def _is_sane_relative_path(value: str) -> bool:
    candidate = value.strip()
    if not candidate or "\x00" in candidate or "\\" in candidate:
        return False
    if candidate.startswith("~") or candidate.startswith("-"):
        return False
    path = PurePosixPath(candidate)
    if path.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _finding(code: str, path: str, message: str) -> CampaignLintFinding:
    return CampaignLintFinding(code=code, path=path, message=message)
