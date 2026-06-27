from __future__ import annotations

import hashlib
import json
import re
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
    primary_spec: Path,
    *,
    write: bool,
) -> CampaignInitResult:
    if not write:
        return _usage_error(
            "write_required",
            "$.write",
            "Campaign init currently requires --write so generated artifacts are lintable.",
        )

    path_text = primary_spec.as_posix()
    if not _is_sane_relative_path(path_text):
        return _usage_error(
            "invalid_primary_spec_path",
            "$.primary_spec",
            "Primary spec path must be a sane relative path.",
        )
    if path_text.startswith(("http://", "https://")):
        return _usage_error(
            "unsupported_primary_spec",
            "$.primary_spec",
            "Campaign init supports local primary spec paths only.",
        )
    if not primary_spec.exists():
        return _usage_error(
            "missing_primary_spec",
            "$.primary_spec",
            f"Primary spec does not exist: {path_text}.",
        )
    if not primary_spec.is_file():
        return _usage_error(
            "invalid_primary_spec",
            "$.primary_spec",
            f"Primary spec must be a file: {path_text}.",
        )

    source_text = primary_spec.read_text(encoding="utf-8")
    source_hash = _sha256_text(source_text)
    slug = _slugify(primary_spec.stem)
    title = _title_from_source(source_text, fallback=primary_spec.stem)
    extracted_sections = _extract_sections(source_text)
    goal_sections = extracted_sections or (
        PrimarySection(
            id="refine-primary-spec",
            title="Refine Primary Spec",
            level=1,
            line=1,
        ),
    )
    markers = _refinement_markers(extracted_sections)

    drafts = _build_artifacts(
        slug=slug,
        title=title,
        primary_spec=primary_spec,
        source_hash=source_hash,
        sections=goal_sections,
        extracted_sections=extracted_sections,
        markers=markers,
    )
    collision = _first_collision(drafts)
    if collision is not None:
        return _usage_error(
            "artifact_exists",
            collision.as_posix(),
            f"Refusing to overwrite existing non-identical artifact: {collision.as_posix()}.",
        )

    for draft in drafts:
        draft.path.parent.mkdir(parents=True, exist_ok=True)
        if not draft.path.exists() or draft.path.read_text(encoding="utf-8") != draft.text:
            draft.path.write_text(draft.text, encoding="utf-8")

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
    lint = _lint_generated(campaign_path, loop_path, goal_paths, evidence_paths)
    valid = _lint_valid(lint)

    payload = {
        "ok": valid,
        "command": "campaign.init",
        "campaign_id": f"CAMPAIGN-{slug}",
        "loop_id": f"LOOP-{slug}",
        "needs_refinement": True,
        "primary_spec": {
            "path": primary_spec.as_posix(),
            "sha256": source_hash,
        },
        "sections": [section.to_dict() for section in extracted_sections],
        "refinement_markers": markers,
        "artifacts": {
            "campaign": campaign_path.as_posix(),
            "loop": loop_path.as_posix(),
            "goals": [path.as_posix() for path in goal_paths],
            "evidence_plans": [path.as_posix() for path in evidence_paths],
            "needs_refinement": f"docs/campaigns/CAMPAIGN-{slug}.needs_refinement.json",
        },
        "lint": lint,
        "message": (
            "Draft campaign scaffold written. Refine semantic decomposition before treating it "
            "as implementation-ready."
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

    for index, section in enumerate(sections, start=1):
        goal_id = f"GOAL-{slug}-{index:03d}"
        evidence_id = f"EVIDENCE-{slug}-{index:03d}"
        goal_path = Path(f"docs/goals/{goal_id}.json")
        evidence_path = Path(f"docs/evidence/{evidence_id}.json")
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
            "reason": "Generated from primary spec headings without semantic decomposition.",
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
    sections: list[PrimarySection] = []
    seen: dict[str, int] = {}
    in_fence = False
    for line_number, line in enumerate(source_text.splitlines(), start=1):
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
        sections.append(PrimarySection(id=section_id, title=title, level=level, line=line_number))
    return tuple(sections)


def _refinement_markers(sections: tuple[PrimarySection, ...]) -> list[dict[str, str]]:
    markers = [
        {
            "route": "needs_specification",
            "reason": "Deterministic scaffold did not perform semantic campaign decomposition.",
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


def _first_collision(drafts: tuple[ArtifactDraft, ...]) -> Path | None:
    for draft in drafts:
        if draft.path.exists() and draft.path.read_text(encoding="utf-8") != draft.text:
            return draft.path
    return None


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
