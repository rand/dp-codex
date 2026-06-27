from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from dp.core.campaign_manifest import lint_campaign_file
from dp.providers.beads import BdUnavailableError, BeadsNotInitializedError, run_bd

# @trace SPEC-80.11
REFINE_MODE = "deterministic_refine"

# @trace SPEC-80.12
LLM_REQUEST_MODE = "llm_request"
LLM_IMPORT_MODE = "llm_import"
LLM_PROMPT_TEMPLATE = "campaign-refine-calling-agent-v0.2"
LLM_RESPONSE_SCHEMA_VERSION = "0.1"
LLM_RESPONSE_SCHEMA_PATH = "docs/schemas/campaign-refine-llm-response.schema.json"
SHELL_CONTROL_PATTERNS = ("&&", "||", ";", "|", "`", "$(", "\n", "\r", ">", "<")
SHELL_EXECUTABLES = frozenset({"bash", "cmd", "fish", "powershell", "pwsh", "sh", "zsh"})
LLM_PROVIDER_SOURCES = frozenset({"calling_agent", "environment", "explicit_config"})


@dataclass(frozen=True)
class CampaignRefineResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class PlannedNode:
    index: int
    goal_path: Path
    evidence_path: Path
    goal: dict[str, Any]
    section_id: str
    title: str
    classification: str
    refinement_state: str
    signals: dict[str, list[str]]
    routes: list[str]
    spec_path: Path
    adr_path: Path | None

    @property
    def goal_id(self) -> str:
        return str(self.goal.get("id", "GOAL-unknown"))

    def spec_item(self) -> dict[str, Any]:
        return {
            "path": self.spec_path.as_posix(),
            "goal_id": self.goal_id,
            "section_id": self.section_id,
            "classification": self.classification,
            "refinement_state": self.refinement_state,
        }

    def adr_item(self) -> dict[str, Any] | None:
        if self.adr_path is None:
            return None
        return {
            "path": self.adr_path.as_posix(),
            "goal_id": self.goal_id,
            "section_id": self.section_id,
            "classification": self.classification,
            "refinement_state": self.refinement_state,
        }


def refine_campaign(
    campaign_path: Path,
    *,
    write: bool,
    create_beads: bool,
    llm: bool,
    llm_response: Path | None = None,
) -> CampaignRefineResult:
    if create_beads and not write:
        return _usage_error(
            "create_beads_requires_write",
            "$.create_beads",
            "--create-beads mutates Beads and requires --write.",
        )
    if llm and write and llm_response is None:
        return _usage_error(
            "llm_response_required_for_write",
            "$.llm_response",
            "--llm writes require an explicit --llm-response artifact.",
        )
    if llm_response is not None and not write:
        return _usage_error(
            "llm_response_requires_write",
            "$.llm_response",
            "--llm-response imports model output and requires --write.",
        )
    if llm_response is not None and create_beads:
        return _usage_error(
            "llm_response_create_beads_unsupported",
            "$.create_beads",
            "--create-beads is not supported while importing an LLM response.",
        )

    lint_result = lint_campaign_file(campaign_path)
    if lint_result.exit_code != 0:
        return CampaignRefineResult(
            payload={
                "ok": False,
                "command": "campaign.refine",
                "lint": lint_result.report.to_dict(),
            },
            exit_code=lint_result.exit_code,
        )

    campaign = _read_json_object(campaign_path)
    campaign_id = str(campaign["id"])
    campaign_slug = _slugify(campaign_id.removeprefix("CAMPAIGN-"))
    planned_nodes = _planned_nodes(campaign, campaign_slug=campaign_slug)
    provenance = _deterministic_provenance(campaign_path, campaign, planned_nodes)
    planned = _planned_payload(planned_nodes)

    if llm_response is not None:
        return _import_llm_response(
            campaign_path,
            campaign,
            planned_nodes,
            planned=planned,
            deterministic_provenance=provenance,
            response_path=llm_response,
        )

    if llm:
        return _emit_llm_request(
            campaign_path,
            campaign,
            planned_nodes,
            planned=planned,
        )

    collisions = _collisions(campaign_id, planned_nodes, provenance)
    if collisions:
        return _usage_error(
            "artifact_exists",
            collisions[0],
            f"Refusing to overwrite existing non-identical artifact: {collisions[0]}.",
        )

    beads_result = _empty_beads_result(requested=create_beads)
    if create_beads:
        beads_result = _create_beads(campaign, campaign_id=campaign_id, planned_nodes=planned_nodes)
        if beads_result.get("ok") is not True:
            return CampaignRefineResult(
                payload={
                    "ok": False,
                    "command": "campaign.refine",
                    "campaign_id": campaign_id,
                    "written": False,
                    "provenance": provenance,
                    "planned": planned,
                    "beads": beads_result,
                },
                exit_code=1,
            )

    if write:
        for node in planned_nodes:
            _write_if_needed(node.spec_path, _render_spec_stub(campaign_id, node, provenance))
            if node.adr_path is not None:
                _write_if_needed(node.adr_path, _render_adr_stub(node))
            _write_goal_refinement(node, provenance)
            _write_evidence_refinement(node, provenance)
        _write_campaign_refinement(
            campaign_path,
            campaign,
            planned_nodes,
            provenance=provenance,
            beads_result=beads_result,
        )

    return CampaignRefineResult(
        payload={
            "ok": True,
            "command": "campaign.refine",
            "campaign_id": campaign_id,
            "mode": REFINE_MODE,
            "written": write,
            "provenance": provenance,
            "planned": planned,
            "beads": beads_result,
            "message": (
                "Campaign refinement planned."
                if not write
                else "Campaign refinement artifacts written."
            ),
        },
        exit_code=0,
    )


def _planned_nodes(campaign: dict[str, Any], *, campaign_slug: str) -> list[PlannedNode]:
    artifacts = campaign.get("artifacts", {})
    goal_paths = artifacts.get("goals", []) if isinstance(artifacts, dict) else []
    next_adr_index = _next_adr_index(Path("docs/adr"))
    planned: list[PlannedNode] = []
    for index, goal_path_text in enumerate(goal_paths, start=1):
        goal_path = Path(str(goal_path_text))
        goal = _read_json_object(goal_path)
        evidence_path = _goal_evidence_path(goal)
        compiler_value = goal.get("compiler")
        compiler: dict[str, Any] = compiler_value if isinstance(compiler_value, dict) else {}
        source_value = goal.get("source")
        source: dict[str, Any] = source_value if isinstance(source_value, dict) else {}
        section_id = _slugify(str(source.get("id") or f"node-{index:03d}"))
        title = str(goal.get("title") or section_id)
        classification = str(compiler.get("classification") or "unknown")
        refinement_state = str(compiler.get("refinement_state") or "needs_specification")
        routes_value = compiler.get("routes")
        routes = routes_value if isinstance(routes_value, list) else []
        signals = _signals(compiler.get("signals"))
        spec_path = Path(f"docs/specs/CAMPAIGN-{campaign_slug}-{index:03d}-{section_id}.md")
        adr_path: Path | None = None
        if refinement_state == "needs_decision" or classification == "decision":
            adr_path = Path(
                f"docs/adr/ADR-{next_adr_index:04d}-{campaign_slug}-{section_id}.md"
            )
            next_adr_index += 1
        planned.append(
            PlannedNode(
                index=index,
                goal_path=goal_path,
                evidence_path=evidence_path,
                goal=goal,
                section_id=section_id,
                title=title,
                classification=classification,
                refinement_state=refinement_state,
                signals=signals,
                routes=[str(route) for route in routes],
                spec_path=spec_path,
                adr_path=adr_path,
            )
        )
    return planned


def _planned_payload(planned_nodes: list[PlannedNode]) -> dict[str, Any]:
    adr_items = [item for node in planned_nodes if (item := node.adr_item()) is not None]
    return {
        "specs": [node.spec_item() for node in planned_nodes],
        "adrs": adr_items,
        "goals": [
            {
                "path": node.goal_path.as_posix(),
                "goal_id": node.goal_id,
                "spec_path": node.spec_path.as_posix(),
                "evidence_path": node.evidence_path.as_posix(),
                "adr_path": node.adr_path.as_posix() if node.adr_path is not None else None,
                "refinement_state": node.refinement_state,
            }
            for node in planned_nodes
        ],
    }


def _deterministic_provenance(
    campaign_path: Path,
    campaign: dict[str, Any],
    planned_nodes: list[PlannedNode],
) -> dict[str, Any]:
    planned_digest = _json_sha256(_planned_payload(planned_nodes))
    return {
        "kind": REFINE_MODE,
        "provider": None,
        "provider_source": None,
        "model": None,
        "network_calls": False,
        "prompt_hash": None,
        "prompt_template": None,
        "input_artifact_hashes": _input_artifact_hashes(campaign_path, campaign, planned_nodes),
        "output_hash": planned_digest,
        "dp_version": "unknown",
        "linter_version": "0.1",
        "reviewed": False,
    }


def _emit_llm_request(
    campaign_path: Path,
    campaign: dict[str, Any],
    planned_nodes: list[PlannedNode],
    *,
    planned: dict[str, Any],
) -> CampaignRefineResult:
    campaign_id = str(campaign["id"])
    request = _llm_request(campaign, planned_nodes)
    input_hashes = _input_artifact_hashes(campaign_path, campaign, planned_nodes)
    provenance = {
        "kind": LLM_REQUEST_MODE,
        "provider": "calling_agent",
        "provider_source": "calling_agent",
        "model": "calling_agent_model",
        "network_calls": False,
        "prompt_hash": request["prompt_hash"],
        "prompt_template": LLM_PROMPT_TEMPLATE,
        "input_artifact_hashes": input_hashes,
        "output_hash": _json_sha256(request),
        "dp_version": "unknown",
        "linter_version": "0.1",
        "reviewed": False,
    }
    return CampaignRefineResult(
        payload={
            "ok": True,
            "command": "campaign.refine",
            "campaign_id": campaign_id,
            "mode": LLM_REQUEST_MODE,
            "written": False,
            "provenance": provenance,
            "planned": planned,
            "beads": _empty_beads_result(requested=False),
            "request": request,
            "message": "LLM refinement request emitted for the calling agent provider.",
        },
        exit_code=0,
    )


def _import_llm_response(
    campaign_path: Path,
    campaign: dict[str, Any],
    planned_nodes: list[PlannedNode],
    *,
    planned: dict[str, Any],
    deterministic_provenance: dict[str, Any],
    response_path: Path,
) -> CampaignRefineResult:
    campaign_id = str(campaign["id"])
    response_result = _read_llm_response(response_path)
    if response_result.exit_code != 0:
        return response_result
    response = response_result.payload["response"]
    request = _llm_request(campaign, planned_nodes)
    errors = _validate_llm_response(response, request, campaign_id, planned_nodes)
    if errors:
        return CampaignRefineResult(
            payload={
                "ok": False,
                "command": "campaign.refine",
                "campaign_id": campaign_id,
                "mode": LLM_IMPORT_MODE,
                "response_path": response_path.as_posix(),
                "errors": errors,
            },
            exit_code=1,
        )

    collisions = _collisions(campaign_id, planned_nodes, deterministic_provenance)
    if collisions:
        return _usage_error(
            "artifact_exists",
            collisions[0],
            f"Refusing to overwrite existing non-identical artifact: {collisions[0]}.",
        )

    provenance = _llm_import_provenance(
        campaign_path,
        campaign,
        planned_nodes,
        response_path=response_path,
        response=response,
        prompt_hash=str(request["prompt_hash"]),
    )
    response_nodes = _response_nodes_by_goal(response)
    for node in planned_nodes:
        _write_if_needed(
            node.spec_path,
            _render_spec_stub(campaign_id, node, deterministic_provenance),
        )
        if node.adr_path is not None:
            _write_if_needed(node.adr_path, _render_adr_stub(node))
        _write_goal_refinement(node, deterministic_provenance)
        _write_evidence_refinement(node, deterministic_provenance)
        if node.goal_id in response_nodes:
            _write_goal_llm_refinement(node, response_nodes[node.goal_id], provenance)
            _write_evidence_llm_refinement(node, response_nodes[node.goal_id], provenance)
    _write_campaign_refinement(
        campaign_path,
        campaign,
        planned_nodes,
        provenance=deterministic_provenance,
        beads_result=_empty_beads_result(requested=False),
    )
    _write_campaign_llm_refinement(
        campaign_path,
        response,
        provenance=provenance,
        response_path=response_path,
    )

    return CampaignRefineResult(
        payload={
            "ok": True,
            "command": "campaign.refine",
            "campaign_id": campaign_id,
            "mode": LLM_IMPORT_MODE,
            "written": True,
            "provenance": provenance,
            "planned": planned,
            "beads": _empty_beads_result(requested=False),
            "llm": {
                "response_path": response_path.as_posix(),
                "imported_nodes": sorted(response_nodes),
            },
            "message": "LLM refinement response imported as draft authoring metadata.",
        },
        exit_code=0,
    )


def _llm_request(campaign: dict[str, Any], planned_nodes: list[PlannedNode]) -> dict[str, Any]:
    campaign_id = str(campaign["id"])
    nodes = [_llm_request_node(node) for node in planned_nodes]
    prompt_inputs = {
        "campaign_id": campaign_id,
        "primary_spec": campaign.get("primary_spec", {}),
        "nodes": nodes,
    }
    prompt = _render_llm_prompt(prompt_inputs)
    prompt_hash = _text_sha256(prompt)
    return {
        "schema_version": LLM_RESPONSE_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "provider": "calling_agent",
        "provider_source": "calling_agent",
        "network_calls_by": "calling_agent",
        "prompt_template": LLM_PROMPT_TEMPLATE,
        "prompt_hash": prompt_hash,
        "response_schema": LLM_RESPONSE_SCHEMA_PATH,
        "prompt": prompt,
        "response_contract": {
            "schema_version": LLM_RESPONSE_SCHEMA_VERSION,
            "required_fields": [
                "schema_version",
                "campaign_id",
                "prompt_hash",
                "provider",
                "provider_source",
                "model",
                "created_at",
                "nodes",
            ],
            "node_fields": [
                "goal_id",
                "objective",
                "rationale",
                "non_goals",
                "requirements",
                "evidence",
                "decisions",
                "dependencies",
                "read_first",
                "allowed_paths",
            ],
        },
        "nodes": nodes,
    }


def _llm_request_node(node: PlannedNode) -> dict[str, Any]:
    return {
        "goal_id": node.goal_id,
        "goal_path": node.goal_path.as_posix(),
        "evidence_path": node.evidence_path.as_posix(),
        "spec_path": node.spec_path.as_posix(),
        "adr_path": node.adr_path.as_posix() if node.adr_path is not None else None,
        "section_id": node.section_id,
        "title": node.title,
        "classification": node.classification,
        "refinement_state": node.refinement_state,
        "routes": node.routes,
        "signals": node.signals,
    }


def _render_llm_prompt(prompt_inputs: dict[str, Any]) -> str:
    return (
        "You are refining a dp-codex campaign scaffold for a disciplined agent workflow.\n"
        "Return JSON only, matching the supplied response contract. Do not include Markdown.\n"
        "Draft semantic authoring metadata only: objectives, rationale, requirements, non-goals, "
        "evidence cues, decisions, dependencies, read-first paths, and allowed paths.\n"
        "Do not claim readiness, completion, verification, or evidence success. Do not propose raw "
        "shell commands. Evidence commands must be argv arrays for registered commands.\n"
        "Campaign inputs:\n"
        f"{json.dumps(prompt_inputs, indent=2, sort_keys=True)}\n"
    )


def _read_llm_response(path: Path) -> CampaignRefineResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _llm_response_input_error(
            "missing_llm_response",
            "$.llm_response",
            f"LLM response file not found: {path.as_posix()}",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _llm_response_input_error(
            "malformed_llm_response",
            "$.llm_response",
            f"LLM response is not valid JSON: line {exc.lineno} column {exc.colno}.",
        )
    if not isinstance(payload, dict):
        return _llm_response_input_error(
            "llm_response_object_required",
            "$.llm_response",
            "LLM response must be a JSON object.",
        )
    return CampaignRefineResult(payload={"response": payload}, exit_code=0)


def _llm_response_input_error(code: str, path: str, message: str) -> CampaignRefineResult:
    return CampaignRefineResult(
        payload={
            "ok": False,
            "command": "campaign.refine",
            "error": {"code": code, "path": path, "message": message},
        },
        exit_code=2,
    )


def _validate_llm_response(
    response: dict[str, Any],
    request: dict[str, Any],
    campaign_id: str,
    planned_nodes: list[PlannedNode],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if response.get("schema_version") != LLM_RESPONSE_SCHEMA_VERSION:
        errors.append(
            _finding(
                "unsupported_llm_response_schema",
                "$.schema_version",
                f"LLM response schema_version must be {LLM_RESPONSE_SCHEMA_VERSION}.",
            )
        )
    if response.get("campaign_id") != campaign_id:
        errors.append(
            _finding(
                "campaign_id_mismatch",
                "$.campaign_id",
                "LLM response campaign_id must match the CampaignManifest.",
            )
        )
    if response.get("prompt_hash") != request["prompt_hash"]:
        errors.append(
            _finding(
                "prompt_hash_mismatch",
                "$.prompt_hash",
                "LLM response prompt_hash must match the current campaign refinement request.",
            )
        )
    for key in ("provider", "model", "created_at"):
        if not isinstance(response.get(key), str) or not response[key]:
            errors.append(
                _finding(
                    f"missing_{key}",
                    f"$.{key}",
                    f"LLM response must define {key}.",
                )
            )
    provider_source = response.get("provider_source")
    if provider_source not in LLM_PROVIDER_SOURCES:
        errors.append(
            _finding(
                "invalid_provider_source",
                "$.provider_source",
                "provider_source must be calling_agent, environment, or explicit_config.",
            )
        )

    known_goals = {node.goal_id for node in planned_nodes}
    seen_goals: set[str] = set()
    nodes = response.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append(_finding("missing_nodes", "$.nodes", "LLM response must include nodes."))
        return errors
    for index, node in enumerate(nodes):
        path = f"$.nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(_finding("node_object_required", path, "Each node must be an object."))
            continue
        goal_id = node.get("goal_id")
        if not isinstance(goal_id, str) or not goal_id:
            errors.append(
                _finding("missing_goal_id", f"{path}.goal_id", "Node must define goal_id.")
            )
        elif goal_id not in known_goals:
            errors.append(
                _finding(
                    "unknown_goal_id",
                    f"{path}.goal_id",
                    f"LLM response references unknown goal_id: {goal_id}.",
                )
            )
        elif goal_id in seen_goals:
            errors.append(
                _finding(
                    "duplicate_goal_id",
                    f"{path}.goal_id",
                    f"LLM response repeats goal_id: {goal_id}.",
                )
            )
        else:
            seen_goals.add(goal_id)
        _validate_string_list(node, "non_goals", f"{path}.non_goals", errors)
        _validate_string_list(node, "requirements", f"{path}.requirements", errors)
        _validate_string_list(node, "decisions", f"{path}.decisions", errors)
        _validate_string_list(node, "dependencies", f"{path}.dependencies", errors)
        _validate_path_list(node, "read_first", f"{path}.read_first", errors)
        _validate_path_list(node, "allowed_paths", f"{path}.allowed_paths", errors)
        _validate_llm_evidence(node.get("evidence"), f"{path}.evidence", errors)
    return errors


def _validate_string_list(
    payload: dict[str, Any],
    key: str,
    path: str,
    errors: list[dict[str, str]],
) -> None:
    value = payload.get(key, [])
    if value is None:
        return
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(_finding("string_list_required", path, f"{key} must be a list of strings."))


def _validate_path_list(
    payload: dict[str, Any],
    key: str,
    path: str,
    errors: list[dict[str, str]],
) -> None:
    value = payload.get(key, [])
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(_finding("path_list_required", path, f"{key} must be a list of paths."))
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not _is_sane_relative_path(item):
            errors.append(
                _finding(
                    "invalid_path",
                    f"{path}[{index}]",
                    f"{key} entries must be sane relative paths.",
                )
            )


def _validate_llm_evidence(
    evidence: Any,
    path: str,
    errors: list[dict[str, str]],
) -> None:
    if evidence is None:
        return
    if not isinstance(evidence, list):
        errors.append(_finding("evidence_list_required", path, "evidence must be a list."))
        return
    for index, item in enumerate(evidence):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(
                _finding(
                    "evidence_object_required",
                    item_path,
                    "Evidence item must be an object.",
                )
            )
            continue
        if item.get("kind") != "registered_command":
            errors.append(
                _finding(
                    "unsupported_evidence_kind",
                    f"{item_path}.kind",
                    "Model-proposed evidence must use kind=registered_command.",
                )
            )
        argv = item.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(part, str) or not part for part in argv)
        ):
            errors.append(
                _finding(
                    "invalid_evidence_argv",
                    f"{item_path}.argv",
                    "Model-proposed evidence argv must be a non-empty string array.",
                )
            )
            continue
        if _argv_contains_raw_shell(argv):
            errors.append(
                _finding(
                    "raw_shell_evidence",
                    f"{item_path}.argv",
                    "Model-proposed evidence must not contain raw shell commands.",
                )
            )


def _llm_import_provenance(
    campaign_path: Path,
    campaign: dict[str, Any],
    planned_nodes: list[PlannedNode],
    *,
    response_path: Path,
    response: dict[str, Any],
    prompt_hash: str,
) -> dict[str, Any]:
    return {
        "kind": "llm",
        "provider": response["provider"],
        "provider_source": response["provider_source"],
        "model": response["model"],
        "network_calls": True,
        "prompt_hash": prompt_hash,
        "prompt_template": LLM_PROMPT_TEMPLATE,
        "input_artifact_hashes": _input_artifact_hashes(campaign_path, campaign, planned_nodes),
        "output_hash": _file_sha256(response_path),
        "dp_version": "unknown",
        "linter_version": "0.1",
        "created_at": response["created_at"],
        "reviewed": False,
    }


def _empty_beads_result(*, requested: bool) -> dict[str, Any]:
    return {
        "requested": requested,
        "created": False,
        "epic_id": None,
        "issue_ids": [],
        "operations": [],
    }


def _create_beads(
    campaign: dict[str, Any],
    *,
    campaign_id: str,
    planned_nodes: list[PlannedNode],
) -> dict[str, Any]:
    artifacts = campaign.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    existing_epics = _string_list(artifacts.get("beads_epics"))
    existing_issues = _string_list(artifacts.get("beads_issues"))
    operations: list[dict[str, Any]] = []

    epic_id = existing_epics[0] if existing_epics else None
    issue_ids = list(existing_issues)
    try:
        if epic_id is None:
            epic_id = _create_beads_issue(
                [
                    "create",
                    f"{campaign_id} campaign refinement",
                    "--type",
                    "epic",
                    "--priority",
                    "P2",
                    "--description",
                    (
                        f"Campaign refinement work materialized from {campaign_id}. "
                        "Generated by dp campaign refine."
                    ),
                    "--acceptance",
                    "Refined campaign artifacts are reviewed and deterministic gates pass.",
                    "--labels",
                    "campaign-control,refinement",
                    "--json",
                ]
            )
            operations.append({"kind": "epic", "id": epic_id})
        for node in planned_nodes[len(existing_issues) :]:
            issue_id = _create_beads_issue(
                [
                    "create",
                    f"Refine {node.goal_id}: {node.title}",
                    "--parent",
                    epic_id,
                    "--type",
                    "task",
                    "--priority",
                    "P2",
                    "--spec-id",
                    "SPEC-80.11",
                    "--description",
                    (
                        f"Review and refine generated campaign node {node.section_id}. "
                        f"Draft spec: {node.spec_path.as_posix()}."
                    ),
                    "--acceptance",
                    "Node artifacts are reviewed, linted, and ready for goal execution.",
                    "--labels",
                    "campaign-control,refinement",
                    "--json",
                ]
            )
            issue_ids.append(issue_id)
            operations.append({"kind": "task", "goal_id": node.goal_id, "id": issue_id})
    except (BdUnavailableError, BeadsNotInitializedError) as exc:
        return {
            "requested": True,
            "created": bool(operations),
            "ok": False,
            "epic_id": epic_id,
            "issue_ids": issue_ids,
            "operations": operations,
            "error": {"code": "beads_unavailable", "message": str(exc)},
        }
    except RuntimeError as exc:
        return {
            "requested": True,
            "created": bool(operations),
            "ok": False,
            "epic_id": epic_id,
            "issue_ids": issue_ids,
            "operations": operations,
            "error": {"code": "beads_create_failed", "message": str(exc)},
        }

    return {
        "requested": True,
        "created": bool(operations),
        "ok": True,
        "epic_id": epic_id,
        "issue_ids": issue_ids,
        "operations": operations,
    }


def _create_beads_issue(command: list[str]) -> str:
    result = run_bd(command)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "bd create failed"
        raise RuntimeError(message)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"bd create did not emit valid JSON: {exc}") from exc
    issue_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(issue_id, str) or not issue_id:
        raise RuntimeError("bd create JSON did not include an id.")
    return issue_id


def _write_campaign_refinement(
    campaign_path: Path,
    campaign: dict[str, Any],
    planned_nodes: list[PlannedNode],
    *,
    provenance: dict[str, Any],
    beads_result: dict[str, Any],
) -> None:
    artifacts = campaign.setdefault("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
        campaign["artifacts"] = artifacts
    _extend_unique(artifacts, "specs", [node.spec_path.as_posix() for node in planned_nodes])
    _extend_unique(
        artifacts,
        "adrs",
        [node.adr_path.as_posix() for node in planned_nodes if node.adr_path is not None],
    )
    if beads_result.get("epic_id") is not None:
        _extend_unique(artifacts, "beads_epics", [str(beads_result["epic_id"])])
    _extend_unique(artifacts, "beads_issues", _string_list(beads_result.get("issue_ids")))
    state = campaign.setdefault("state", {})
    if isinstance(state, dict):
        state["status"] = "draft"
    campaign["refinement"] = {
        "mode": REFINE_MODE,
        "provenance": provenance,
        "specs": [node.spec_item() for node in planned_nodes],
        "adrs": [item for node in planned_nodes if (item := node.adr_item()) is not None],
        "beads": beads_result,
    }
    _write_json(campaign_path, campaign)


def _write_goal_refinement(node: PlannedNode, provenance: dict[str, Any]) -> None:
    goal = dict(node.goal)
    goal["refinement"] = {
        "state": node.refinement_state,
        "classification": node.classification,
        "spec_path": node.spec_path.as_posix(),
        "adr_path": node.adr_path.as_posix() if node.adr_path is not None else None,
        "routes": node.routes,
        "signals": node.signals,
        "provenance": provenance,
    }
    _write_json(node.goal_path, goal)


def _write_evidence_refinement(node: PlannedNode, provenance: dict[str, Any]) -> None:
    evidence_plan = _read_json_object(node.evidence_path)
    evidence_plan["refinement"] = {
        "state": node.refinement_state,
        "classification": node.classification,
        "goal_id": node.goal_id,
        "goal_path": node.goal_path.as_posix(),
        "spec_path": node.spec_path.as_posix(),
        "adr_path": node.adr_path.as_posix() if node.adr_path is not None else None,
        "routes": node.routes,
        "signals": node.signals,
        "provenance": provenance,
    }
    _write_json(node.evidence_path, evidence_plan)


def _write_goal_llm_refinement(
    node: PlannedNode,
    response_node: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    goal = _read_json_object(node.goal_path)
    refinement = goal.setdefault("refinement", {})
    if not isinstance(refinement, dict):
        refinement = {}
        goal["refinement"] = refinement
    refinement["llm"] = _llm_node_metadata(response_node, provenance)
    _write_json(node.goal_path, goal)


def _write_evidence_llm_refinement(
    node: PlannedNode,
    response_node: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    evidence_plan = _read_json_object(node.evidence_path)
    refinement = evidence_plan.setdefault("refinement", {})
    if not isinstance(refinement, dict):
        refinement = {}
        evidence_plan["refinement"] = refinement
    refinement["llm"] = {
        "goal_id": node.goal_id,
        "evidence": _llm_evidence(response_node),
        "provenance": provenance,
    }
    _write_json(node.evidence_path, evidence_plan)


def _write_campaign_llm_refinement(
    campaign_path: Path,
    response: dict[str, Any],
    *,
    provenance: dict[str, Any],
    response_path: Path,
) -> None:
    campaign = _read_json_object(campaign_path)
    state = campaign.setdefault("state", {})
    if isinstance(state, dict):
        state["status"] = "draft"
    refinement = campaign.setdefault("refinement", {})
    if not isinstance(refinement, dict):
        refinement = {}
        campaign["refinement"] = refinement
    refinement["llm"] = {
        "mode": LLM_IMPORT_MODE,
        "response_path": response_path.as_posix(),
        "campaign_rationale": response.get("campaign_rationale"),
        "nodes": [
            {
                "goal_id": node.get("goal_id"),
                "objective": node.get("objective"),
                "rationale": node.get("rationale"),
            }
            for node in response.get("nodes", [])
            if isinstance(node, dict)
        ],
        "provenance": provenance,
    }
    _write_json(campaign_path, campaign)


def _llm_node_metadata(response_node: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": response_node.get("objective"),
        "rationale": response_node.get("rationale"),
        "non_goals": _string_list(response_node.get("non_goals")),
        "requirements": _string_list(response_node.get("requirements")),
        "evidence": _llm_evidence(response_node),
        "decisions": _string_list(response_node.get("decisions")),
        "dependencies": _string_list(response_node.get("dependencies")),
        "read_first": _string_list(response_node.get("read_first")),
        "allowed_paths": _string_list(response_node.get("allowed_paths")),
        "provenance": provenance,
    }


def _llm_evidence(response_node: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = response_node.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [item for item in evidence if isinstance(item, dict)]


def _goal_evidence_path(goal: dict[str, Any]) -> Path:
    evidence = goal.get("evidence")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("evidence_plan"), str):
        raise ValueError("GoalContract does not include an evidence.evidence_plan path.")
    return Path(evidence["evidence_plan"])


def _render_spec_stub(campaign_id: str, node: PlannedNode, provenance: dict[str, Any]) -> str:
    return (
        f"# Draft Spec: {node.title}\n\n"
        "Status: draft\n"
        f"Campaign: {campaign_id}\n"
        f"Goal: {node.goal_id}\n"
        f"Generated-By: {provenance['kind']}\n\n"
        "## Intent\n\n"
        f"Refine campaign node `{node.section_id}` into implementation-ready work.\n\n"
        "## Compiler Classification\n\n"
        f"- Classification: `{node.classification}`\n"
        f"- Refinement state: `{node.refinement_state}`\n"
        f"- Routes: {', '.join(node.routes) if node.routes else 'none'}\n\n"
        "## Extracted Signals\n\n"
        + _render_signal_list(node.signals)
        + "\n## Required Refinement\n\n"
        "- Replace this stub with reviewed requirements, non-goals, and acceptance criteria.\n"
        "- Keep deterministic gates responsible for readiness and completion.\n"
    )


def _render_adr_stub(node: PlannedNode) -> str:
    if node.adr_path is None:
        raise ValueError("ADR stub rendering requires an ADR path.")
    adr_id = node.adr_path.name.split("-", 2)[0] + "-" + node.adr_path.name.split("-", 2)[1]
    return (
        "---\n"
        f"id: {adr_id}\n"
        f"title: Decide refinement path for {node.title}\n"
        "status: proposal\n"
        "created: 1970-01-01\n"
        "updated: 1970-01-01\n"
        "superseded_by: \n"
        "---\n\n"
        "## Context\n\n"
        f"- Campaign node `{node.section_id}` contains decision, risk, or blocker cues.\n"
        f"- Goal: `{node.goal_id}`.\n\n"
        "## Decision\n\n"
        "- TBD by reviewed authoring work.\n\n"
        "## Consequences\n\n"
        "- The associated goal should remain draft until this decision is resolved.\n"
    )


def _render_signal_list(signals: dict[str, list[str]]) -> str:
    chunks: list[str] = []
    for key in ("requirements", "evidence", "decisions", "blockers", "dependencies"):
        values = signals.get(key, [])
        chunks.append(f"### {key.replace('_', ' ').title()}\n\n")
        if values:
            chunks.extend(f"- {value}\n" for value in values)
        else:
            chunks.append("- none\n")
        chunks.append("\n")
    return "".join(chunks)


def _collisions(
    campaign_id: str,
    planned_nodes: list[PlannedNode],
    provenance: dict[str, Any],
) -> list[str]:
    collisions: list[str] = []
    for node in planned_nodes:
        spec_text = _render_spec_stub(campaign_id, node, provenance)
        if node.spec_path.exists() and node.spec_path.read_text(encoding="utf-8") != spec_text:
            collisions.append(node.spec_path.as_posix())
        if node.adr_path is not None:
            adr_text = _render_adr_stub(node)
            if node.adr_path.exists() and node.adr_path.read_text(encoding="utf-8") != adr_text:
                collisions.append(node.adr_path.as_posix())
    return collisions


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path.as_posix()}.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_if_needed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def _extend_unique(payload: dict[str, Any], key: str, values: list[str]) -> None:
    existing = _string_list(payload.get(key))
    for value in values:
        if value not in existing:
            existing.append(value)
    payload[key] = existing


def _signals(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        value = {}
    return {
        "requirements": _string_list(value.get("requirements")),
        "evidence": _string_list(value.get("evidence")),
        "decisions": _string_list(value.get("decisions")),
        "blockers": _string_list(value.get("blockers")),
        "dependencies": _string_list(value.get("dependencies")),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _response_nodes_by_goal(response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = response.get("nodes")
    if not isinstance(nodes, list):
        return {}
    return {
        str(node["goal_id"]): node
        for node in nodes
        if isinstance(node, dict) and isinstance(node.get("goal_id"), str)
    }


def _input_artifact_hashes(
    campaign_path: Path,
    campaign: dict[str, Any],
    planned_nodes: list[PlannedNode],
) -> dict[str, str]:
    input_hashes: dict[str, str] = {
        "campaign": _file_sha256(campaign_path),
    }
    primary_spec = campaign.get("primary_spec")
    if isinstance(primary_spec, dict) and isinstance(primary_spec.get("path"), str):
        primary_path = Path(primary_spec["path"])
        if primary_path.exists():
            input_hashes["primary_spec"] = _file_sha256(primary_path)
    for node in planned_nodes:
        input_hashes[node.goal_path.as_posix()] = _file_sha256(node.goal_path)
        input_hashes[node.evidence_path.as_posix()] = _file_sha256(node.evidence_path)
    return input_hashes


def _argv_contains_raw_shell(argv: list[str]) -> bool:
    executable = Path(argv[0]).name.lower()
    if executable in SHELL_EXECUTABLES:
        return True
    return any(any(pattern in part for pattern in SHELL_CONTROL_PATTERNS) for part in argv)


def _is_sane_relative_path(value: str) -> bool:
    if not value or value.startswith(("/", "~", "http://", "https://")):
        return False
    parts = Path(value).parts
    return ".." not in parts


def _finding(code: str, path: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "path": path,
        "message": message,
    }


def _next_adr_index(directory: Path) -> int:
    max_index = 0
    if directory.exists():
        for path in directory.glob("ADR-*.md"):
            parts = path.name.split("-", 2)
            if len(parts) >= 2 and parts[1].isdigit():
                max_index = max(max_index, int(parts[1]))
    return max_index + 1


def _slugify(value: str) -> str:
    result = "".join(character.lower() if character.isalnum() else "-" for character in value)
    while "--" in result:
        result = result.replace("--", "-")
    return result.strip("-") or "campaign"


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _text_sha256(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def _json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _usage_error(code: str, path: str, message: str) -> CampaignRefineResult:
    return CampaignRefineResult(
        payload={
            "ok": False,
            "command": "campaign.refine",
            "error": {
                "code": code,
                "path": path,
                "message": message,
            },
        },
        exit_code=2,
    )
