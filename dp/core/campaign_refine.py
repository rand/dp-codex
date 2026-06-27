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
LLM_PROMPT_TEMPLATE = "campaign-refine-calling-agent-v0.1"


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
) -> CampaignRefineResult:
    if llm:
        return _llm_not_implemented(campaign_path)
    if create_beads and not write:
        return _usage_error(
            "create_beads_requires_write",
            "$.create_beads",
            "--create-beads mutates Beads and requires --write.",
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

    planned_digest = _json_sha256(_planned_payload(planned_nodes))
    return {
        "kind": REFINE_MODE,
        "provider": None,
        "provider_source": None,
        "model": None,
        "network_calls": False,
        "prompt_hash": None,
        "prompt_template": None,
        "input_artifact_hashes": input_hashes,
        "output_hash": planned_digest,
        "dp_version": "unknown",
        "linter_version": "0.1",
        "reviewed": False,
    }


def _llm_not_implemented(campaign_path: Path) -> CampaignRefineResult:
    input_hashes: dict[str, str] = {}
    if campaign_path.exists():
        input_hashes["campaign"] = _file_sha256(campaign_path)
    return CampaignRefineResult(
        payload={
            "ok": False,
            "command": "campaign.refine",
            "error": {
                "code": "llm_refine_not_implemented",
                "path": "$.llm",
                "message": (
                    "LLM-assisted campaign refinement is an explicit authoring mode, "
                    "but no calling-agent provider adapter is implemented yet."
                ),
            },
            "provenance": {
                "kind": "llm",
                "provider": "calling_agent",
                "provider_source": "calling_agent",
                "model": "unknown",
                "network_calls": True,
                "prompt_hash": None,
                "prompt_template": LLM_PROMPT_TEMPLATE,
                "input_artifact_hashes": input_hashes,
                "output_hash": None,
                "dp_version": "unknown",
                "linter_version": "0.1",
                "reviewed": False,
            },
        },
        exit_code=2,
    )


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


def _json_sha256(payload: dict[str, Any]) -> str:
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
