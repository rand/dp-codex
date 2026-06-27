from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from dp.core.campaign_manifest import lint_campaign_file
from dp.core.evidence_lint import lint_evidence_file
from dp.core.goal_lint import lint_goal_file
from dp.core.loop_ledger import lint_loop_file

# @trace SPEC-80.16
READINESS_MODE = "deterministic_campaign_ready"
PROMOTABLE_STATUSES = frozenset({"draft", "ready"})
UNRESOLVED_STATES = frozenset(
    {
        "needs_refinement",
        "needs_specification",
        "needs_decision",
        "needs_validator",
        "draft_placeholder",
        "blocked",
    }
)
UNRESOLVED_ROUTES = frozenset(
    {"needs_specification", "needs_decision", "needs_validator", "unsafe_scope"}
)


@dataclass(frozen=True)
class ReadinessFinding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class CampaignReadyResult:
    payload: dict[str, Any]
    exit_code: int


def ready_campaign(campaign_path: Path, *, write: bool) -> CampaignReadyResult:
    lint_result = lint_campaign_file(campaign_path)
    checks = [{"name": "campaign_lint", "ok": lint_result.exit_code == 0}]
    if lint_result.exit_code != 0:
        return CampaignReadyResult(
            payload={
                "ok": False,
                "command": "campaign.ready",
                "campaign_id": lint_result.report.campaign_id,
                "write": write,
                "written": False,
                "ready": False,
                "checks": checks,
                "errors": lint_result.report.to_dict()["errors"],
                "warnings": lint_result.report.to_dict()["warnings"],
            },
            exit_code=lint_result.exit_code,
        )

    campaign = _read_json_object(campaign_path)
    campaign_id = str(campaign["id"])
    before_status = _campaign_status(campaign)
    errors: list[ReadinessFinding] = []
    warnings: list[ReadinessFinding] = []
    artifact_paths = _artifact_paths(campaign)

    if before_status not in PROMOTABLE_STATUSES:
        errors.append(
            _finding(
                "campaign_state_not_promotable",
                "$.state.status",
                "Campaign readiness can only promote draft or already-ready campaigns.",
            )
        )

    checks.extend(_lint_artifacts(artifact_paths, errors))
    _validate_graph(campaign, artifact_paths=artifact_paths, errors=errors, warnings=warnings)
    checks.append({"name": "graph_readiness", "ok": not errors})

    ready = not errors
    readiness = _readiness_metadata(
        campaign_path,
        campaign,
        artifact_paths=artifact_paths,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )

    written = False
    after_status = "ready" if ready and write else before_status
    if ready and write:
        campaign.setdefault("state", {})["status"] = "ready"
        campaign["readiness"] = readiness
        compiler = campaign.get("compiler")
        if isinstance(compiler, dict):
            compiler["ready_for_implementation"] = True
        _write_json(campaign_path, campaign)
        written = True

    payload = {
        "ok": ready,
        "command": "campaign.ready",
        "campaign_id": campaign_id,
        "write": write,
        "written": written,
        "ready": ready,
        "state": {"before": before_status, "after": after_status},
        "readiness": readiness,
        "checks": checks,
        "errors": [error.to_dict() for error in errors],
        "warnings": [warning.to_dict() for warning in warnings],
    }
    return CampaignReadyResult(payload=payload, exit_code=0 if ready else 1)


def _lint_artifacts(
    artifact_paths: dict[str, list[str]],
    errors: list[ReadinessFinding],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    loop_ok = True
    for index, loop_path in enumerate(artifact_paths["loops"]):
        loop_result = lint_loop_file(Path(loop_path))
        if loop_result.exit_code != 0:
            loop_ok = False
            errors.append(
                _finding(
                    "loop_lint_failed",
                    f"$.artifacts.loops[{index}]",
                    f"LoopLedger must pass lint before readiness: {loop_path}.",
                )
            )
    checks.append({"name": "loop_lint", "ok": loop_ok})

    goal_ok = True
    for index, goal_path in enumerate(artifact_paths["goals"]):
        goal_result = lint_goal_file(Path(goal_path))
        if goal_result.exit_code != 0:
            goal_ok = False
            errors.append(
                _finding(
                    "goal_lint_failed",
                    f"$.artifacts.goals[{index}]",
                    f"GoalContract must pass lint before readiness: {goal_path}.",
                )
            )
    checks.append({"name": "goal_lint", "ok": goal_ok})

    evidence_ok = True
    for index, evidence_path in enumerate(artifact_paths["evidence_plans"]):
        evidence_result = lint_evidence_file(Path(evidence_path))
        if evidence_result.exit_code != 0:
            evidence_ok = False
            errors.append(
                _finding(
                    "evidence_lint_failed",
                    f"$.artifacts.evidence_plans[{index}]",
                    f"EvidencePlan must pass lint before readiness: {evidence_path}.",
                )
            )
    checks.append({"name": "evidence_lint", "ok": evidence_ok})
    return checks


def _validate_graph(
    campaign: dict[str, Any],
    *,
    artifact_paths: dict[str, list[str]],
    errors: list[ReadinessFinding],
    warnings: list[ReadinessFinding],
) -> None:
    del warnings
    declared_specs = set(artifact_paths["specs"])
    declared_adrs = set(artifact_paths["adrs"])
    declared_evidence = set(artifact_paths["evidence_plans"])

    if campaign.get("needs_refinement"):
        errors.append(
            _finding(
                "unresolved_refinement_state",
                "$.needs_refinement",
                "Campaign still contains needs_refinement markers.",
            )
        )
    _validate_campaign_compiler(campaign, errors)

    loops = [_read_json_object(Path(loop_path)) for loop_path in artifact_paths["loops"]]
    goal_payloads = {
        goal_path: _read_json_object(Path(goal_path)) for goal_path in artifact_paths["goals"]
    }
    evidence_payloads = {
        evidence_path: _read_json_object(Path(evidence_path))
        for evidence_path in artifact_paths["evidence_plans"]
    }
    node_refs = _node_refs(loops)

    for loop_index, loop in enumerate(loops):
        nodes = loop.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node_index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            node_path = f"$.artifacts.loops[{loop_index}].nodes[{node_index}]"
            _validate_node(
                node,
                node_path=node_path,
                declared_specs=declared_specs,
                declared_adrs=declared_adrs,
                declared_evidence=declared_evidence,
                goal_payloads=goal_payloads,
                evidence_payloads=evidence_payloads,
                node_refs=node_refs,
                errors=errors,
            )


def _validate_campaign_compiler(
    campaign: dict[str, Any],
    errors: list[ReadinessFinding],
) -> None:
    compiler = campaign.get("compiler")
    if not isinstance(compiler, dict):
        return
    nodes = compiler.get("nodes")
    if not isinstance(nodes, list):
        return
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        _validate_metadata_state(
            node,
            path=f"$.compiler.nodes[{index}]",
            errors=errors,
        )


def _validate_node(
    node: dict[str, Any],
    *,
    node_path: str,
    declared_specs: set[str],
    declared_adrs: set[str],
    declared_evidence: set[str],
    goal_payloads: dict[str, dict[str, Any]],
    evidence_payloads: dict[str, dict[str, Any]],
    node_refs: dict[str, str],
    errors: list[ReadinessFinding],
) -> None:
    goal_id = _string(node.get("goal_id"))
    goal_path = _string(node.get("goal_path"))
    evidence_path = _string(node.get("evidence_plan"))
    node_id = _string(node.get("id"))
    depends_on = _string_list(node.get("depends_on"))

    if evidence_path is None:
        errors.append(
            _finding(
                "missing_node_evidence",
                f"{node_path}.evidence_plan",
                "Loop node must declare an EvidencePlan before campaign readiness.",
            )
        )
    elif evidence_path not in declared_evidence:
        errors.append(
            _finding(
                "node_evidence_not_declared",
                f"{node_path}.evidence_plan",
                "Loop node EvidencePlan must be declared in the CampaignManifest.",
            )
        )
    if _string(node.get("beads_issue_id")) is None:
        errors.append(
            _finding(
                "missing_beads_issue",
                f"{node_path}.beads_issue_id",
                "Loop node must link to a Beads issue before campaign readiness.",
            )
        )

    if goal_path is None:
        return
    goal = goal_payloads.get(goal_path)
    if goal is None:
        return

    if goal.get("needs_refinement"):
        errors.append(
            _finding(
                "unresolved_refinement_state",
                f"{node_path}.goal_path",
                "GoalContract still contains needs_refinement markers.",
            )
        )
    _validate_goal_metadata(goal, node_path=node_path, errors=errors)

    if evidence_path is not None:
        _validate_evidence_alignment(
            goal,
            evidence_path=evidence_path,
            goal_id=goal_id,
            node_path=node_path,
            evidence_payloads=evidence_payloads,
            errors=errors,
        )

    _validate_child_spec(
        goal,
        declared_specs=declared_specs,
        node_path=node_path,
        errors=errors,
    )
    _validate_decision_adr(
        goal,
        declared_adrs=declared_adrs,
        node_path=node_path,
        errors=errors,
    )
    _validate_llm_dependencies(
        goal,
        current_node_id=node_id,
        depends_on=depends_on,
        node_refs=node_refs,
        node_path=node_path,
        errors=errors,
    )


def _validate_goal_metadata(
    goal: dict[str, Any],
    *,
    node_path: str,
    errors: list[ReadinessFinding],
) -> None:
    compiler = goal.get("compiler")
    if isinstance(compiler, dict):
        _validate_metadata_state(compiler, path=f"{node_path}.goal.compiler", errors=errors)
    refinement = goal.get("refinement")
    if isinstance(refinement, dict):
        _validate_metadata_state(
            refinement,
            path=f"{node_path}.goal.refinement",
            errors=errors,
        )


def _validate_evidence_alignment(
    goal: dict[str, Any],
    *,
    evidence_path: str,
    goal_id: str | None,
    node_path: str,
    evidence_payloads: dict[str, dict[str, Any]],
    errors: list[ReadinessFinding],
) -> None:
    evidence = evidence_payloads.get(evidence_path)
    if evidence is None:
        return
    if goal_id is not None and evidence.get("goal_id") != goal_id:
        errors.append(
            _finding(
                "node_evidence_mismatch",
                f"{node_path}.evidence_plan",
                "Loop node EvidencePlan goal_id must match node goal_id.",
            )
        )
    goal_evidence = goal.get("evidence")
    goal_evidence_path = (
        goal_evidence.get("evidence_plan") if isinstance(goal_evidence, dict) else None
    )
    if goal_evidence_path != evidence_path:
        errors.append(
            _finding(
                "goal_evidence_mismatch",
                f"{node_path}.goal_path",
                "GoalContract evidence.evidence_plan must match the loop node EvidencePlan.",
            )
        )
    refinement = evidence.get("refinement")
    if isinstance(refinement, dict):
        _validate_metadata_state(
            refinement,
            path=f"{node_path}.evidence.refinement",
            errors=errors,
        )


def _validate_child_spec(
    goal: dict[str, Any],
    *,
    declared_specs: set[str],
    node_path: str,
    errors: list[ReadinessFinding],
) -> None:
    spec_path = _goal_spec_path(goal)
    if spec_path is None or spec_path not in declared_specs or not Path(spec_path).exists():
        errors.append(
            _finding(
                "missing_child_spec",
                node_path,
                "Loop node must have a declared child spec before campaign readiness.",
            )
        )


def _validate_decision_adr(
    goal: dict[str, Any],
    *,
    declared_adrs: set[str],
    node_path: str,
    errors: list[ReadinessFinding],
) -> None:
    refinement = goal.get("refinement")
    compiler = goal.get("compiler")
    decision_like = False
    adr_path: str | None = None
    for metadata in (compiler, refinement):
        if not isinstance(metadata, dict):
            continue
        if metadata.get("classification") == "decision":
            decision_like = True
        if "needs_decision" in _string_list(metadata.get("routes")):
            decision_like = True
        candidate = _string(metadata.get("adr_path"))
        if candidate is not None:
            adr_path = candidate
    if not decision_like:
        return
    if adr_path is None or adr_path not in declared_adrs or not Path(adr_path).exists():
        errors.append(
            _finding(
                "missing_decision_adr",
                node_path,
                "Decision-like loop node must have a declared ADR before campaign readiness.",
            )
        )


def _validate_metadata_state(
    metadata: dict[str, Any],
    *,
    path: str,
    errors: list[ReadinessFinding],
) -> None:
    state = _string(metadata.get("state")) or _string(metadata.get("refinement_state"))
    if state in UNRESOLVED_STATES:
        errors.append(
            _finding(
                "unresolved_refinement_state",
                path,
                f"Readiness is blocked by unresolved refinement state: {state}.",
            )
        )
    routes = _string_list(metadata.get("routes"))
    unresolved_routes = sorted(route for route in routes if route in UNRESOLVED_ROUTES)
    if unresolved_routes:
        errors.append(
            _finding(
                "unresolved_refinement_state",
                f"{path}.routes",
                "Readiness is blocked by unresolved route(s): "
                + ", ".join(unresolved_routes)
                + ".",
            )
        )


def _validate_llm_dependencies(
    goal: dict[str, Any],
    *,
    current_node_id: str | None,
    depends_on: list[str],
    node_refs: dict[str, str],
    node_path: str,
    errors: list[ReadinessFinding],
) -> None:
    refinement = goal.get("refinement")
    if not isinstance(refinement, dict):
        return
    llm = refinement.get("llm")
    if not isinstance(llm, dict):
        return
    dependencies = _string_list(llm.get("dependencies"))
    for index, dependency in enumerate(dependencies):
        dependency_node = node_refs.get(dependency)
        if dependency_node is None or dependency_node == current_node_id:
            errors.append(
                _finding(
                    "llm_dependency_not_materialized",
                    f"{node_path}.goal.refinement.llm.dependencies[{index}]",
                    "LLM dependency hint must resolve to another loop node and be materialized "
                    "in depends_on before readiness.",
                )
            )
            continue
        if dependency_node not in depends_on:
            errors.append(
                _finding(
                    "llm_dependency_not_materialized",
                    f"{node_path}.goal.refinement.llm.dependencies[{index}]",
                    "LLM dependency hint must be materialized as a LoopLedger depends_on edge.",
                )
            )


def _node_refs(loops: list[dict[str, Any]]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for loop in loops:
        nodes = loop.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = _string(node.get("id"))
            if node_id is None:
                continue
            for value in (
                node_id,
                _string(node.get("goal_id")),
                _string(node.get("goal_path")),
                _string(node.get("evidence_plan")),
            ):
                if value is not None:
                    refs[value] = node_id
    return refs


def _goal_spec_path(goal: dict[str, Any]) -> str | None:
    refinement = goal.get("refinement")
    if isinstance(refinement, dict):
        spec_path = _string(refinement.get("spec_path"))
        if spec_path is not None:
            return spec_path
    source = goal.get("source")
    if isinstance(source, dict):
        return _string(source.get("path"))
    return None


def _readiness_metadata(
    campaign_path: Path,
    campaign: dict[str, Any],
    *,
    artifact_paths: dict[str, list[str]],
    checks: list[dict[str, Any]],
    errors: list[ReadinessFinding],
    warnings: list[ReadinessFinding],
) -> dict[str, Any]:
    input_hashes = _input_artifact_hashes(campaign_path, artifact_paths)
    material = {
        "campaign_id": campaign.get("id"),
        "input_artifact_hashes": input_hashes,
        "checks": checks,
        "errors": [error.to_dict() for error in errors],
        "warnings": [warning.to_dict() for warning in warnings],
    }
    return {
        "mode": READINESS_MODE,
        "network_calls": False,
        "llm_judgment": False,
        "provenance": {
            "kind": READINESS_MODE,
            "provider": None,
            "model": None,
            "network_calls": False,
            "input_artifact_hashes": input_hashes,
            "output_hash": _json_sha256(material),
            "linter_version": "0.1",
        },
    }


def _input_artifact_hashes(
    campaign_path: Path,
    artifact_paths: dict[str, list[str]],
) -> dict[str, str]:
    paths = [campaign_path.as_posix()]
    for field in ("specs", "adrs", "goals", "evidence_plans", "loops"):
        paths.extend(artifact_paths[field])
    unique_paths = sorted(set(paths))
    return {
        path: _file_sha256(Path(path)) for path in unique_paths if Path(path).is_file()
    }


def _artifact_paths(campaign: dict[str, Any]) -> dict[str, list[str]]:
    artifacts = campaign.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    return {
        "specs": _string_list(artifacts.get("specs")),
        "adrs": _string_list(artifacts.get("adrs")),
        "goals": _string_list(artifacts.get("goals")),
        "evidence_plans": _string_list(artifacts.get("evidence_plans")),
        "loops": _string_list(artifacts.get("loops")),
    }


def _campaign_status(campaign: dict[str, Any]) -> str | None:
    state = campaign.get("state")
    if not isinstance(state, dict):
        return None
    return _string(state.get("status"))


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path.as_posix()}.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _finding(code: str, path: str, message: str) -> ReadinessFinding:
    return ReadinessFinding(code=code, path=path, message=message)


def _is_sane_relative_path(value: str) -> bool:
    if not value or value.startswith(("/", "~", "http://", "https://", "-")):
        return False
    parsed = PurePosixPath(value)
    return ".." not in parsed.parts
