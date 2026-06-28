from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from dp.core.campaign_manifest import lint_campaign_file
from dp.core.evidence_lint import lint_evidence_file
from dp.core.goal_lint import lint_goal_file
from dp.core.loop_ledger import lint_loop_file

# @trace SPEC-80.07
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
DECISION_TERMS = ("decision", "decisions", "question", "questions", "risk", "risks", "tradeoff")
VALIDATOR_TERMS = ("acceptance", "evidence", "proof", "test", "tests", "validation", "verification")

# @trace SPEC-80.09
COMPILER_MODE = "deterministic_markdown_signals"
BLOCKER_TERMS = ("blocked", "blocker", "missing", "tbd", "unclear", "unknown")
DEPENDENCY_TERMS = ("after", "before", "blocked by", "depend", "depends", "only after")
IMPLEMENTATION_TERMS = (
    "artifact",
    "campaign",
    "cli",
    "code",
    "command",
    "compile",
    "goal",
    "implement",
    "schema",
    "validator",
)
REQUIREMENT_TERMS = (
    "acceptance",
    "must",
    "need",
    "needs",
    "require",
    "required",
    "requires",
    "shall",
    "should",
)
EVIDENCE_SIGNAL_TERMS = (
    "acceptance",
    "check",
    "evidence",
    "lint",
    "make check",
    "proof",
    "pytest",
    "test",
    "tests",
    "typecheck",
    "validation",
    "verification",
    "verify",
)
MAX_SIGNAL_CUES = 8
MAX_SIGNAL_CHARS = 220
MAX_PUBLIC_ITEMS = 25


@dataclass(frozen=True)
class CampaignInitResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class PrimarySection:
    id: str
    title: str
    level: int
    line: int
    body: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "line": self.line,
        }


@dataclass(frozen=True)
class ArtifactDraft:
    path: Path
    payload: dict[str, Any]

    @property
    def text(self) -> str:
        return json.dumps(self.payload, indent=2, sort_keys=True) + "\n"


def init_campaign_from_primary_spec(
    primary_spec: str | Path,
    *,
    write: bool,
) -> CampaignInitResult:
    source_input = str(primary_spec)
    if _looks_like_url(source_input):
        return _usage_error(
            "unsupported_primary_spec_source",
            "$.primary_spec",
            "Campaign init supports local primary spec paths only; URL adapters are not enabled.",
        )

    primary_spec_path = Path(source_input)
    path_text = primary_spec_path.as_posix()
    if not _is_sane_relative_path(path_text):
        return _usage_error(
            "invalid_primary_spec_path",
            "$.primary_spec",
            "Primary spec path must be a sane relative path.",
        )
    if not primary_spec_path.exists():
        return _usage_error(
            "missing_primary_spec",
            "$.primary_spec",
            f"Primary spec does not exist: {path_text}.",
        )
    if not primary_spec_path.is_file():
        return _usage_error(
            "invalid_primary_spec",
            "$.primary_spec",
            f"Primary spec must be a file: {path_text}.",
        )

    source_text = primary_spec_path.read_text(encoding="utf-8")
    source_hash = _sha256_text(source_text)
    slug = _slugify(primary_spec_path.stem)
    title = _title_from_source(source_text, fallback=primary_spec_path.stem)
    extracted_sections = _extract_sections(source_text)
    goal_sections = extracted_sections or (
        PrimarySection(
            id="refine-primary-spec",
            title="Refine Primary Spec",
            level=1,
            line=1,
            body=source_text,
        ),
    )
    compiler = _compile_primary_spec_signals(goal_sections, extracted_sections=extracted_sections)
    markers = _refinement_markers(extracted_sections, compiler=compiler)

    drafts = _build_artifacts(
        slug=slug,
        title=title,
        primary_spec=primary_spec_path,
        source_hash=source_hash,
        sections=goal_sections,
        extracted_sections=extracted_sections,
        markers=markers,
        compiler=compiler,
    )

    campaign_path = Path(f"docs/campaigns/CAMPAIGN-{slug}.json")
    loop_path = Path(f"docs/loops/LOOP-{slug}.json")
    goal_paths = [
        Path(f"docs/goals/GOAL-{slug}-{index:03d}.json")
        for index in range(1, len(goal_sections) + 1)
    ]
    evidence_paths = [
        Path(f"docs/evidence/EVIDENCE-{slug}-{index:03d}.json")
        for index in range(1, len(goal_sections) + 1)
    ]
    collisions = _collisions(drafts)
    if write and collisions:
        collision = collisions[0]
        return _usage_error(
            "artifact_exists",
            collision.as_posix(),
            f"Refusing to overwrite existing non-identical artifact: {collision.as_posix()}.",
        )

    if write:
        _write_drafts(drafts)
        lint = _lint_generated(campaign_path, loop_path, goal_paths, evidence_paths)
    else:
        lint = _lint_drafts(
            drafts,
            primary_spec=primary_spec_path,
            source_text=source_text,
            campaign_path=campaign_path,
            loop_path=loop_path,
            goal_paths=goal_paths,
            evidence_paths=evidence_paths,
        )
    valid = _lint_valid(lint)
    sections_public, sections_truncated = _bounded_items(
        [section.to_dict() for section in extracted_sections]
    )
    compiler_public = _public_compiler(compiler)

    payload = {
        "ok": valid,
        "command": "campaign.init",
        "campaign_id": f"CAMPAIGN-{slug}",
        "loop_id": f"LOOP-{slug}",
        "write": write,
        "written": write,
        "preview": not write,
        "needs_refinement": True,
        "primary_spec": {
            "kind": "local_path",
            "path": primary_spec_path.as_posix(),
            "sha256": source_hash,
        },
        "section_count": len(extracted_sections),
        "sections_truncated": sections_truncated,
        "sections": sections_public,
        "compiler": compiler_public,
        "refinement_markers": markers,
        "artifacts": {
            "campaign": campaign_path.as_posix(),
            "loop": loop_path.as_posix(),
            "goals": [path.as_posix() for path in goal_paths],
            "goal_count": len(goal_paths),
            "evidence_plans": [path.as_posix() for path in evidence_paths],
            "evidence_plan_count": len(evidence_paths),
            "needs_refinement": f"docs/campaigns/CAMPAIGN-{slug}.needs_refinement.json",
        },
        "collisions": [path.as_posix() for path in collisions],
        "lint": lint,
        "next_commands": {
            "write": (
                f"dp campaign init --primary-spec {primary_spec_path.as_posix()} --write --json"
            ),
            "refine": f"dp campaign refine {campaign_path.as_posix()} --write --json",
            "ready": f"dp campaign ready {campaign_path.as_posix()} --write --json",
        },
        "message": (
            "Draft campaign scaffold planned. Use --write to create artifacts, then refine "
            "semantic decomposition before treating it as implementation-ready."
            if not write
            else "Draft campaign scaffold written. Refine semantic decomposition before treating "
            "it as implementation-ready."
        ),
    }
    return CampaignInitResult(payload=payload, exit_code=0 if valid else 1)


def _build_artifacts(
    *,
    slug: str,
    title: str,
    primary_spec: Path,
    source_hash: str,
    sections: tuple[PrimarySection, ...],
    extracted_sections: tuple[PrimarySection, ...],
    markers: list[dict[str, str]],
    compiler: dict[str, Any],
) -> tuple[ArtifactDraft, ...]:
    campaign_id = f"CAMPAIGN-{slug}"
    loop_id = f"LOOP-{slug}"
    campaign_path = Path(f"docs/campaigns/{campaign_id}.json")
    loop_path = Path(f"docs/loops/{loop_id}.json")
    marker_path = Path(f"docs/campaigns/{campaign_id}.needs_refinement.json")

    goals: list[ArtifactDraft] = []
    evidence_plans: list[ArtifactDraft] = []
    loop_nodes: list[dict[str, Any]] = []
    goal_paths: list[str] = []
    evidence_paths: list[str] = []

    compiler_nodes = {
        str(node["section_id"]): node
        for node in compiler.get("nodes", [])
        if isinstance(node, dict)
    }

    for index, section in enumerate(sections, start=1):
        goal_id = f"GOAL-{slug}-{index:03d}"
        evidence_id = f"EVIDENCE-{slug}-{index:03d}"
        goal_path = Path(f"docs/goals/{goal_id}.json")
        evidence_path = Path(f"docs/evidence/{evidence_id}.json")
        compiler_node = compiler_nodes.get(section.id, _empty_compiler_node(section))
        goal_paths.append(goal_path.as_posix())
        evidence_paths.append(evidence_path.as_posix())
        goals.append(
            ArtifactDraft(
                path=goal_path,
                payload=_goal_payload(
                    goal_id=goal_id,
                    evidence_path=evidence_path,
                    section=section,
                    primary_spec=primary_spec,
                    source_hash=source_hash,
                    slug=slug,
                    compiler_node=compiler_node,
                ),
            )
        )
        evidence_plans.append(
            ArtifactDraft(
                path=evidence_path,
                payload=_evidence_payload(
                    evidence_id=evidence_id,
                    goal_id=goal_id,
                    goal_path=goal_path,
                    evidence_path=evidence_path,
                ),
            )
        )
        loop_nodes.append(
            {
                "id": section.id,
                "kind": "goal",
                "goal_id": goal_id,
                "goal_path": goal_path.as_posix(),
                "depends_on": [],
                "evidence_plan": evidence_path.as_posix(),
                "classification": compiler_node["classification"],
                "refinement_state": compiler_node["refinement_state"],
                "dependency_cues": compiler_node["signals"]["dependencies"],
            }
        )

    loop = ArtifactDraft(
        path=loop_path,
        payload={
            "schema_version": "0.1",
            "id": loop_id,
            "title": f"{title} campaign scaffold loop",
            "source": {
                "kind": "primary_spec",
                "path": primary_spec.as_posix(),
                "input_hash": source_hash,
            },
            "scheduler": "goal_events",
            "context_policy": "fresh_context_per_goal",
            "compiler": _compiler_artifact_summary(compiler),
            "nodes": loop_nodes,
            "stop_rules": [
                "stop on missing required decision",
                "stop on missing evidence surface",
                "stop on unsafe scope expansion",
                "stop when refinement requires semantic judgment",
            ],
        },
    )
    campaign = ArtifactDraft(
        path=campaign_path,
        payload={
            "schema_version": "0.1",
            "id": campaign_id,
            "title": f"{title} campaign scaffold",
            "primary_spec": {
                "path": primary_spec.as_posix(),
                "input_hash": source_hash,
            },
            "artifacts": {
                "specs": [],
                "adrs": [],
                "goals": goal_paths,
                "evidence_plans": evidence_paths,
                "loops": [loop_path.as_posix()],
                "beads_epics": [],
                "beads_issues": [],
            },
            "state": {
                "status": "draft",
                "current_loop": loop_id,
                "current_goal": None,
            },
            "compiler": _compiler_artifact_summary(compiler),
            "needs_refinement": {
                "path": marker_path.as_posix(),
                "routes": sorted({marker["route"] for marker in markers}),
            },
        },
    )
    marker = ArtifactDraft(
        path=marker_path,
        payload={
            "schema_version": "0.1",
            "campaign_id": campaign_id,
            "primary_spec": {
                "path": primary_spec.as_posix(),
                "input_hash": source_hash,
            },
            "needs_refinement": True,
            "sections": [section.to_dict() for section in extracted_sections],
            "compiler": compiler,
            "markers": markers,
        },
    )
    return (campaign, loop, marker, *goals, *evidence_plans)


def _goal_payload(
    *,
    goal_id: str,
    evidence_path: Path,
    section: PrimarySection,
    primary_spec: Path,
    source_hash: str,
    slug: str,
    compiler_node: dict[str, Any],
) -> dict[str, Any]:
    goal_lint_command = f"dp goal lint docs/goals/{goal_id}.json --json"
    evidence_lint_command = f"dp evidence lint {evidence_path.as_posix()} --json"
    return {
        "schema_version": "0.1",
        "id": goal_id,
        "title": f"Refine primary spec section: {section.title}",
        "source": {
            "kind": "primary_spec_section",
            "id": section.id,
            "path": primary_spec.as_posix(),
            "input_hash": source_hash,
            "line": section.line,
        },
        "level": "node",
        "objective": (
            f"Refine the primary spec section '{section.title}' into implementation-ready "
            "child specs, GoalContracts, evidence plans, and acceptance checks that pass "
            "deterministic dp lint gates."
        ),
        "evidence": {
            "evidence_plan": evidence_path.as_posix(),
            "verification_commands": [
                goal_lint_command,
                evidence_lint_command,
            ],
            "trace_ids": ["SPEC-80.07"],
        },
        "boundaries": {
            "read_first": [primary_spec.as_posix()],
            "preferred_paths": [
                "docs/specs",
                "docs/goals",
                "docs/evidence",
                "docs/loops",
                "docs/campaigns",
            ],
            "allowed_paths": ["docs"],
            "forbidden_paths": [],
            "allowed_commands": [
                goal_lint_command,
                evidence_lint_command,
                "make check",
            ],
        },
        "iteration_policy": {
            "mode": "smallest_relevant_check_first",
            "max_attempts": 5,
            "after_each_attempt": [
                "run generated artifact lint",
                "repair deterministic failures",
                "record unresolved semantic questions as refinement markers",
            ],
        },
        "terminal_states": {
            "success": (
                "Refined artifacts pass deterministic dp lint and verification gates with "
                "evidence-backed acceptance criteria."
            ),
            "blocked": (
                "Required semantic decomposition, validator design, or decision context is "
                "missing."
            ),
            "budget_exhausted": "Iteration budget is exhausted without refined lintable artifacts.",
            "unsafe_scope": "Required changes exceed the generated scaffold boundaries.",
        },
        "blocked_routes": {
            "needs_specification": {
                "action": "create_spec_stub",
                "also_create_beads_issue": True,
            },
            "needs_decision": {
                "action": "create_adr_stub",
                "also_create_beads_issue": True,
            },
            "needs_validator": {
                "action": "create_evidence_stub",
                "also_create_beads_issue": True,
            },
            "unsafe_scope": {
                "action": "create_scope_decision",
                "also_create_beads_issue": True,
            },
        },
        "needs_refinement": {
            "campaign_slug": slug,
            "reason": (
                "Generated from deterministic primary-spec signals; "
                "authoring refinement remains required."
            ),
        },
        "compiler": {
            "mode": COMPILER_MODE,
            "classification": compiler_node["classification"],
            "refinement_state": compiler_node["refinement_state"],
            "routes": compiler_node["routes"],
            "signals": compiler_node["signals"],
        },
    }


def _evidence_payload(
    *,
    evidence_id: str,
    goal_id: str,
    goal_path: Path,
    evidence_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "id": evidence_id,
        "goal_id": goal_id,
        "checks": [
            {
                "id": "goal-contract-lint",
                "kind": "registered_command",
                "argv": ["dp", "goal", "lint", goal_path.as_posix(), "--json"],
                "timeout_seconds": 30,
                "success_exit_codes": [0],
                "assertions": [
                    {"type": "stdout_json"},
                    {"type": "json_path_equals", "path": "$.valid", "value": True},
                ],
                "mutation_policy": "read_only",
            },
            {
                "id": "evidence-plan-lint",
                "kind": "registered_command",
                "argv": ["dp", "evidence", "lint", evidence_path.as_posix(), "--json"],
                "timeout_seconds": 30,
                "success_exit_codes": [0],
                "assertions": [
                    {"type": "stdout_json"},
                    {"type": "json_path_equals", "path": "$.valid", "value": True},
                ],
                "mutation_policy": "read_only",
            },
        ],
    }


def _extract_sections(source_text: str) -> tuple[PrimarySection, ...]:
    heading_sections: list[PrimarySection] = []
    seen: dict[str, int] = {}
    in_fence = False
    lines = source_text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_PATTERN.match(stripped)
        if match is None:
            continue
        level = len(match.group(1))
        if level != 2:
            continue
        title = match.group(2).strip()
        base_slug = _slugify(title)
        count = seen.get(base_slug, 0) + 1
        seen[base_slug] = count
        section_id = base_slug if count == 1 else f"{base_slug}-{count}"
        heading_sections.append(
            PrimarySection(id=section_id, title=title, level=level, line=line_number)
        )

    sections: list[PrimarySection] = []
    for index, section in enumerate(heading_sections):
        next_line = (
            heading_sections[index + 1].line
            if index + 1 < len(heading_sections)
            else len(lines) + 1
        )
        body = "\n".join(lines[section.line: next_line - 1]).strip()
        sections.append(
            PrimarySection(
                id=section.id,
                title=section.title,
                level=section.level,
                line=section.line,
                body=body,
            )
        )
    return tuple(sections)


def _compile_primary_spec_signals(
    sections: tuple[PrimarySection, ...],
    *,
    extracted_sections: tuple[PrimarySection, ...],
) -> dict[str, Any]:
    nodes = [_compiler_node(section) for section in sections]
    summary = {
        "sections": len(extracted_sections),
        "implementation_candidates": sum(
            1 for node in nodes if node["refinement_state"] == "implementation_candidate"
        ),
        "evidence_candidates": sum(
            1 for node in nodes if node["refinement_state"] == "evidence_candidate"
        ),
        "decision_nodes": sum(1 for node in nodes if node["classification"] == "decision"),
        "needs_specification": sum(
            1 for node in nodes if node["refinement_state"] == "needs_specification"
        ),
        "needs_validator": sum(
            1 for node in nodes if node["refinement_state"] == "needs_validator"
        ),
        "dependency_cues": sum(len(node["signals"]["dependencies"]) for node in nodes),
    }
    return {
        "mode": COMPILER_MODE,
        "llm": False,
        "semantic_planning": False,
        "ready_for_implementation": False,
        "summary": summary,
        "nodes": nodes,
    }


def _compiler_node(section: PrimarySection) -> dict[str, Any]:
    signals = _section_signals(section)
    classification = _section_classification(section, signals)
    refinement_state = _section_refinement_state(classification, signals)
    return {
        "section_id": section.id,
        "title": section.title,
        "line": section.line,
        "classification": classification,
        "refinement_state": refinement_state,
        "routes": _routes_for_refinement_state(refinement_state),
        "signals": signals,
    }


def _section_signals(section: PrimarySection) -> dict[str, list[str]]:
    title_and_body = f"{section.title}\n{section.body}"
    return {
        "requirements": _signal_lines(title_and_body, REQUIREMENT_TERMS),
        "evidence": _signal_lines(title_and_body, EVIDENCE_SIGNAL_TERMS),
        "decisions": _signal_lines(title_and_body, DECISION_TERMS),
        "blockers": _signal_lines(title_and_body, BLOCKER_TERMS),
        "dependencies": _signal_lines(title_and_body, DEPENDENCY_TERMS),
    }


def _signal_lines(text: str, terms: tuple[str, ...]) -> list[str]:
    cues: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = _clean_signal_line(raw_line)
        if not line or line in seen:
            continue
        lowered = line.lower()
        if any(term in lowered for term in terms):
            seen.add(line)
            cues.append(line)
        if len(cues) >= MAX_SIGNAL_CUES:
            break
    return cues


def _clean_signal_line(value: str) -> str:
    stripped = value.strip()
    stripped = re.sub(r"^[-*+]\s+", "", stripped)
    stripped = re.sub(r"^\d+[.)]\s+", "", stripped)
    stripped = re.sub(r"\s+", " ", stripped)
    if len(stripped) > MAX_SIGNAL_CHARS:
        return stripped[: MAX_SIGNAL_CHARS - 3].rstrip() + "..."
    return stripped


def _section_classification(section: PrimarySection, signals: dict[str, list[str]]) -> str:
    title = section.title.lower()
    body = section.body.lower()
    if signals["decisions"]:
        return "decision"
    if any(term in title for term in EVIDENCE_SIGNAL_TERMS):
        return "evidence"
    if any(term in title for term in ("background", "context", "overview", "motivation")):
        return "context"
    if signals["requirements"] or any(term in f"{title}\n{body}" for term in IMPLEMENTATION_TERMS):
        return "implementation"
    return "unknown"


def _section_refinement_state(
    classification: str,
    signals: dict[str, list[str]],
) -> str:
    if classification == "decision" or signals["blockers"]:
        return "needs_decision"
    if classification == "evidence":
        return "evidence_candidate"
    if signals["requirements"] and signals["evidence"]:
        return "implementation_candidate"
    if signals["requirements"]:
        return "needs_validator"
    return "needs_specification"


def _routes_for_refinement_state(refinement_state: str) -> list[str]:
    if refinement_state == "needs_decision":
        return ["needs_decision"]
    if refinement_state == "needs_validator":
        return ["needs_validator"]
    if refinement_state == "needs_specification":
        return ["needs_specification"]
    return []


def _empty_compiler_node(section: PrimarySection) -> dict[str, Any]:
    return {
        "section_id": section.id,
        "title": section.title,
        "line": section.line,
        "classification": "unknown",
        "refinement_state": "needs_specification",
        "routes": ["needs_specification"],
        "signals": {
            "requirements": [],
            "evidence": [],
            "decisions": [],
            "blockers": [],
            "dependencies": [],
        },
    }


def _compiler_artifact_summary(compiler: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": compiler["mode"],
        "llm": compiler["llm"],
        "semantic_planning": compiler["semantic_planning"],
        "ready_for_implementation": compiler["ready_for_implementation"],
        "summary": compiler["summary"],
    }


def _refinement_markers(
    sections: tuple[PrimarySection, ...],
    *,
    compiler: dict[str, Any],
) -> list[dict[str, str]]:
    markers = [
        {
            "route": "needs_specification",
            "reason": (
                "Deterministic compiler extracted signals but did not author child specs, ADRs, "
                "validators, Beads issues, or final implementation goals."
            ),
        }
    ]
    titles = " ".join(section.title.lower() for section in sections)
    if not sections:
        markers.append(
            {
                "route": "needs_specification",
                "reason": "Primary spec has no major Markdown sections to map into goals.",
            }
        )
    if not any(term in titles for term in VALIDATOR_TERMS):
        markers.append(
            {
                "route": "needs_validator",
                "reason": (
                    "Extracted headings do not identify evidence, tests, validation, "
                    "verification, acceptance, or proof."
                ),
            }
        )
    if any(term in titles for term in DECISION_TERMS):
        markers.append(
            {
                "route": "needs_decision",
                "reason": (
                    "Extracted headings indicate decisions, risks, tradeoffs, or open "
                    "questions."
                ),
            }
        )
    for node in compiler.get("nodes", []):
        if not isinstance(node, dict):
            continue
        section_title = str(node.get("title", "unknown section"))
        for route in node.get("routes", []):
            if route == "needs_specification":
                reason = f"Section '{section_title}' needs implementation-specific decomposition."
            elif route == "needs_validator":
                reason = f"Section '{section_title}' has requirements but no evidence cues."
            elif route == "needs_decision":
                reason = f"Section '{section_title}' contains decision, risk, or blocker cues."
            else:
                continue
            markers.append({"route": route, "reason": reason})
    return _deduplicate_markers(markers)


def _deduplicate_markers(markers: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for marker in markers:
        key = (marker["route"], marker["reason"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(marker)
    return unique


def _lint_generated(
    campaign_path: Path,
    loop_path: Path,
    goal_paths: list[Path],
    evidence_paths: list[Path],
) -> dict[str, Any]:
    return {
        "campaign": lint_campaign_file(campaign_path).report.to_dict(),
        "loop": lint_loop_file(loop_path).report.to_dict(),
        "goals": [
            {
                "path": path.as_posix(),
                "report": lint_goal_file(path).report.to_dict(),
            }
            for path in goal_paths
        ],
        "evidence_plans": [
            {
                "path": path.as_posix(),
                "report": lint_evidence_file(path).report.to_dict(),
            }
            for path in evidence_paths
        ],
    }


def _lint_drafts(
    drafts: tuple[ArtifactDraft, ...],
    *,
    primary_spec: Path,
    source_text: str,
    campaign_path: Path,
    loop_path: Path,
    goal_paths: list[Path],
    evidence_paths: list[Path],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dp-campaign-init-") as temp_dir:
        temp_root = Path(temp_dir)
        primary_target = temp_root / primary_spec
        primary_target.parent.mkdir(parents=True, exist_ok=True)
        primary_target.write_text(source_text, encoding="utf-8")
        for draft in drafts:
            target = temp_root / draft.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(draft.text, encoding="utf-8")

        previous_cwd = Path.cwd()
        try:
            os.chdir(temp_root)
            return _lint_generated(campaign_path, loop_path, goal_paths, evidence_paths)
        finally:
            os.chdir(previous_cwd)


def _lint_valid(lint: dict[str, Any]) -> bool:
    campaign = lint["campaign"]
    loop = lint["loop"]
    goals = lint["goals"]
    evidence_plans = lint["evidence_plans"]
    return (
        isinstance(campaign, dict)
        and campaign.get("valid") is True
        and isinstance(loop, dict)
        and loop.get("valid") is True
        and all(item["report"].get("valid") is True for item in goals)
        and all(item["report"].get("valid") is True for item in evidence_plans)
    )


def _collisions(drafts: tuple[ArtifactDraft, ...]) -> list[Path]:
    collisions: list[Path] = []
    for draft in drafts:
        if draft.path.exists() and draft.path.read_text(encoding="utf-8") != draft.text:
            collisions.append(draft.path)
    return collisions


def _write_drafts(drafts: tuple[ArtifactDraft, ...]) -> None:
    for draft in drafts:
        draft.path.parent.mkdir(parents=True, exist_ok=True)
        if not draft.path.exists() or draft.path.read_text(encoding="utf-8") != draft.text:
            draft.path.write_text(draft.text, encoding="utf-8")


def _bounded_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    return items[:MAX_PUBLIC_ITEMS], len(items) > MAX_PUBLIC_ITEMS


def _public_compiler(compiler: dict[str, Any]) -> dict[str, Any]:
    nodes = compiler.get("nodes", [])
    public = dict(compiler)
    if isinstance(nodes, list):
        public["node_count"] = len(nodes)
        public["nodes_truncated"] = len(nodes) > MAX_PUBLIC_ITEMS
        public["nodes"] = nodes[:MAX_PUBLIC_ITEMS]
    else:
        public["node_count"] = 0
        public["nodes_truncated"] = False
        public["nodes"] = []
    return public


def _title_from_source(source_text: str, *, fallback: str) -> str:
    in_fence = False
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_PATTERN.match(stripped)
        if match is not None and len(match.group(1)) == 1:
            return match.group(2).strip()
    return fallback.strip() or "Primary Spec"


def _sha256_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _slugify(value: str) -> str:
    slug = SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return slug or "primary-spec"


def _is_sane_relative_path(value: str) -> bool:
    candidate = value.strip()
    if not candidate or "\x00" in candidate or "\\" in candidate:
        return False
    if candidate.startswith(("~", "-", "http://", "https://")):
        return False
    path = PurePosixPath(candidate)
    if path.is_absolute():
        return False
    if any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _usage_error(code: str, path: str, message: str) -> CampaignInitResult:
    return CampaignInitResult(
        payload={
            "ok": False,
            "command": "campaign.init",
            "error": {
                "code": code,
                "path": path,
                "message": message,
            },
        },
        exit_code=2,
    )
