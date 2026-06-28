from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dp.core.agent_response import next_action
from dp.core.hints import hint_payload
from dp.core.instructions import audit_instructions, inspect_instructions
from dp.core.skills import scaffold_skills

INSPECT_SCHEMA_VERSION = "dp.adopt.inspect.v1"
PLAN_SCHEMA_VERSION = "dp.adoption_plan.v1"
APPLY_SCHEMA_VERSION = "dp.adopt.apply.v1"
VERIFY_SCHEMA_VERSION = "dp.adopt.verify.v1"


@dataclass(frozen=True)
class AdoptionCommandResult:
    payload: dict[str, Any]
    exit_code: int


def inspect_adoption(repo_root: Path | None = None) -> AdoptionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    signals = _adoption_signals(root)
    classification = _classify(signals)
    hints = _adoption_hints(classification, signals)
    payload = {
        "schema_version": INSPECT_SCHEMA_VERSION,
        "status": "ok",
        "classification": classification,
        "repo_root": root.as_posix(),
        "signals": signals,
        "hints": hints,
        "next_actions": _adoption_next_actions(classification),
    }
    return AdoptionCommandResult(payload=payload, exit_code=0)


def plan_adoption(
    repo_root: Path | None = None,
    *,
    write: bool = False,
) -> AdoptionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    inspect_result = inspect_adoption(root)
    audit_result = audit_instructions(root)
    source_state = inspect_result.payload
    plan_id = f"MIGRATION-{_today_slug()}-agent-experience"
    changes = _planned_changes(source_state)
    conflicts = _adoption_conflicts(audit_result.payload["findings"])
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "id": plan_id,
        "status": "planned",
        "source_state": {
            "classification": source_state["classification"],
            "has_agents_md": source_state["signals"]["has_agents_md"],
            "has_agent_bootstrap_guidance": source_state["signals"][
                "has_agent_bootstrap_guidance"
            ],
            "has_campaigns": source_state["signals"]["has_campaigns"],
            "has_legacy_verify": source_state["signals"]["has_legacy_verify"],
            "has_spec81": source_state["signals"]["has_spec81"],
        },
        "changes": changes,
        "conflicts": conflicts,
        "verification": [
            "dp instructions audit --json",
            "dp agent bootstrap --json --detail brief",
            "dp doctor --json",
            "dp adopt verify --json",
        ],
        "rules": {
            "additive_by_default": True,
            "overwrite_agents_md": False,
            "create_agents_override": False,
            "apply_requires_explicit_flag": True,
        },
    }
    artifacts: list[dict[str, Any]] = []
    if write:
        migration_dir = root / "docs/migrations"
        migration_dir.mkdir(parents=True, exist_ok=True)
        json_path = migration_dir / f"{plan_id}.json"
        md_path = migration_dir / f"{plan_id}.md"
        json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_path.write_text(_plan_markdown(plan), encoding="utf-8")
        artifacts.extend(
            [
                {"kind": "adoption_plan", "path": json_path.relative_to(root).as_posix()},
                {"kind": "adoption_plan_markdown", "path": md_path.relative_to(root).as_posix()},
            ]
        )

    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "ok": True,
        "status": "planned",
        "write": write,
        "plan": plan,
        "artifacts": artifacts,
        "hints": _adoption_hints(str(source_state["classification"]), source_state["signals"]),
        "next_actions": [
            next_action(
                "review_plan",
                f"Review docs/migrations/{plan_id}.json before applying.",
                "Adoption plans are reviewable artifacts, not hidden mutations.",
            ),
            next_action(
                "verify_adoption",
                "dp adopt verify --json",
                "Check the project after planned adoption work.",
            ),
        ],
    }
    return AdoptionCommandResult(payload=payload, exit_code=0)


def apply_adoption(
    plan_path: Path,
    *,
    apply: bool = False,
    repo_root: Path | None = None,
) -> AdoptionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _adoption_error("missing_plan", f"Plan file not found: {plan_path.as_posix()}")
    except json.JSONDecodeError as exc:
        return _adoption_error("malformed_plan", f"Plan JSON is malformed at line {exc.lineno}.")

    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        return _adoption_error("unsupported_plan", "Plan must use schema dp.adoption_plan.v1.")

    conflicts = plan.get("conflicts")
    if isinstance(conflicts, list) and conflicts:
        return AdoptionCommandResult(
            payload={
                "schema_version": APPLY_SCHEMA_VERSION,
                "ok": False,
                "status": "blocked",
                "dry_run": not apply,
                "plan": plan_path.as_posix(),
                "conflicts": conflicts,
                "message": "Adoption apply stops on conflicts.",
                "hints": [hint_payload("DP-HINT-INSTRUCTIONS-CONFLICT")],
            },
            exit_code=1,
        )

    changes_value = plan.get("changes")
    changes = changes_value if isinstance(changes_value, list) else []
    applied: list[dict[str, Any]] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        mode = str(change.get("mode") or "propose")
        path = str(change.get("path") or "")
        if mode != "apply":
            applied.append({"id": change.get("id"), "path": path, "status": "preview_only"})
            continue
        if not apply:
            applied.append({"id": change.get("id"), "path": path, "status": "would_apply"})
            continue
        kind = str(change.get("kind") or "")
        if kind == "mkdir" and path:
            (root / path).mkdir(parents=True, exist_ok=True)
            applied.append({"id": change.get("id"), "path": path, "status": "applied"})
        elif kind == "file" and path == "dp-policy.json" and change.get("id") == "create-policy":
            policy_path = root / path
            if policy_path.exists():
                applied.append(
                    {"id": change.get("id"), "path": path, "status": "skipped_existing"}
                )
            else:
                policy_path.write_text('{\n  "mode": "guided"\n}\n', encoding="utf-8")
                applied.append({"id": change.get("id"), "path": path, "status": "applied"})
        elif (
            kind == "command"
            and change.get("command") == "dp skills scaffold --target repo --json"
        ):
            skill_result = scaffold_skills(root, target="repo")
            applied.append(
                {
                    "id": change.get("id"),
                    "path": path,
                    "status": "applied" if skill_result.exit_code == 0 else "failed",
                    "written_count": len(skill_result.payload.get("written", [])),
                    "skipped_count": len(skill_result.payload.get("skipped", [])),
                }
            )
            if skill_result.exit_code != 0:
                return AdoptionCommandResult(
                    payload={
                        "schema_version": APPLY_SCHEMA_VERSION,
                        "ok": False,
                        "status": "failed",
                        "dry_run": False,
                        "plan": plan_path.as_posix(),
                        "applied": applied,
                        "error": skill_result.payload.get("error"),
                    },
                    exit_code=skill_result.exit_code,
                )
        else:
            applied.append(
                {
                    "id": change.get("id"),
                    "path": path,
                    "status": "unsupported_apply_change",
                    "kind": kind,
                }
            )
            return AdoptionCommandResult(
                payload={
                    "schema_version": APPLY_SCHEMA_VERSION,
                    "ok": False,
                    "status": "failed",
                    "dry_run": False,
                    "plan": plan_path.as_posix(),
                    "applied": applied,
                    "error": {
                        "code": "unsupported_apply_change",
                        "message": (
                            "Adoption apply only supports known local deterministic changes."
                        ),
                    },
                },
                exit_code=2,
            )

    payload = {
        "schema_version": APPLY_SCHEMA_VERSION,
        "ok": True,
        "status": "dry_run" if not apply else "applied",
        "dry_run": not apply,
        "plan": plan_path.as_posix(),
        "applied": applied,
        "message": (
            "Dry-run only; pass --apply to apply explicit apply-mode changes."
            if not apply
            else "Adoption plan applied."
        ),
        "hints": [hint_payload("DP-HINT-ADOPTION-PLAN-REQUIRED")] if not apply else [],
    }
    return AdoptionCommandResult(payload=payload, exit_code=0)


def verify_adoption(repo_root: Path | None = None) -> AdoptionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    inspect_result = inspect_adoption(root)
    instruction_result = inspect_instructions(root, detail="brief")
    audit_result = audit_instructions(root)
    checks = [
        {
            "id": "adoption_classified",
            "ok": inspect_result.payload["classification"] != "unknown",
            "summary": f"classification={inspect_result.payload['classification']}",
        },
        {
            "id": "instructions_discoverable",
            "ok": "files" in instruction_result.payload,
            "summary": "instruction inspection succeeded",
        },
        {
            "id": "instruction_audit_available",
            "ok": audit_result.exit_code == 0,
            "summary": "instruction audit completed",
        },
        {
            "id": "policy_known",
            "ok": bool(inspect_result.payload["signals"]["has_policy"]),
            "summary": (
                "dp-policy.json present" if (root / "dp-policy.json").exists() else "no policy"
            ),
        },
    ]
    ok = all(check["ok"] for check in checks[:3])
    payload = {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "ok": ok,
        "status": "ok" if ok else "incomplete",
        "checks": checks,
        "classification": inspect_result.payload["classification"],
        "hints": inspect_result.payload["hints"],
    }
    return AdoptionCommandResult(payload=payload, exit_code=0 if ok else 1)


def _adoption_signals(root: Path) -> dict[str, Any]:
    policy = _load_policy(root / "dp-policy.json")
    md_with_old_commands = _docs_with_old_commands(root)
    return {
        "has_policy": (root / "dp-policy.json").exists(),
        "policy_version": policy.get("schema_version") or policy.get("version"),
        "has_agents_md": (root / "AGENTS.md").exists(),
        "has_agent_bootstrap_guidance": "dp agent bootstrap"
        in _read_text(root / "AGENTS.md").lower(),
        "has_agents_override": (root / "AGENTS.override.md").exists(),
        "has_legacy_verify": (root / "docs/verify/manifest.json").exists(),
        "has_legacy_decompose": any(
            (root / item).exists() for item in ("docs/decompose", "docs/decompositions")
        ),
        "has_goal_artifacts": (root / "docs/goals").exists(),
        "has_evidence_artifacts": (root / "docs/evidence").exists(),
        "has_loop_artifacts": (root / "docs/loops").exists(),
        "has_campaigns": (root / "docs/campaigns").exists(),
        "has_goal_event_dir": (root / ".dp/goals").exists(),
        "has_campaign_event_dir": (root / ".dp/campaigns").exists(),
        "has_hooks": (root / "hooks").exists() or (root / ".git/hooks").exists(),
        "has_codex_hooks": (root / ".codex/hooks.json").exists(),
        "has_skills": (root / ".agents/skills").exists(),
        "has_spec80": (
            root / "docs/specs/SPEC-80-agent-campaign-control-plane-for-dp-codex.md"
        ).exists(),
        "has_spec81": _has_spec81_surface(root),
        "old_command_docs": md_with_old_commands,
        "missing_spec80_structures": _missing_spec80_structures(root),
        "missing_spec81_structures": _missing_spec81_structures(root),
    }


def _classify(signals: dict[str, Any]) -> str:
    if signals["has_spec81"]:
        return "current_spec81"
    if signals["has_spec80"] or signals["has_campaigns"]:
        return "current_spec80"
    if signals["has_goal_artifacts"] or signals["has_loop_artifacts"]:
        return "partial_spec80"
    if signals["has_policy"] or signals["has_legacy_verify"] or signals["has_legacy_decompose"]:
        return "legacy_dp"
    if not any(
        bool(signals[key])
        for key in (
            "has_policy",
            "has_agents_md",
            "has_goal_artifacts",
            "has_campaigns",
            "has_skills",
        )
    ):
        return "not_adopted"
    return "unknown"


def _planned_changes(source_state: dict[str, Any]) -> list[dict[str, Any]]:
    signals = source_state["signals"]
    changes: list[dict[str, Any]] = []
    if not signals["has_policy"]:
        changes.append(
            {
                "id": "create-policy",
                "kind": "file",
                "path": "dp-policy.json",
                "mode": "apply",
                "reason": "Create minimal guided dp policy for verification and local gates.",
            }
        )
    if not signals["has_goal_event_dir"]:
        changes.append(
            {
                "id": "create-goal-event-dir",
                "kind": "mkdir",
                "path": ".dp/goals",
                "mode": "apply",
                "reason": "Enable append-only goal lifecycle events.",
            }
        )
    if not signals["has_campaign_event_dir"]:
        changes.append(
            {
                "id": "create-campaign-event-dir",
                "kind": "mkdir",
                "path": ".dp/campaigns",
                "mode": "apply",
                "reason": "Enable append-only campaign handoff events.",
            }
        )
    if not signals["has_agents_md"]:
        changes.append(
            {
                "id": "create-agents-md",
                "kind": "file",
                "path": "AGENTS.md",
                "mode": "propose",
                "reason": "Add minimal repo instructions after review.",
            }
        )
    elif not signals["has_agent_bootstrap_guidance"]:
        changes.append(
            {
                "id": "patch-agents-md",
                "kind": "patch",
                "path": "AGENTS.md",
                "mode": "propose",
                "reason": "Add a compact dp section without replacing project law.",
            }
        )
    if not signals["has_skills"]:
        changes.append(
            {
                "id": "scaffold-repo-skills",
                "kind": "command",
                "path": ".agents/skills",
                "mode": "apply",
                "command": "dp skills scaffold --target repo --json",
                "reason": "Install focused repo-scoped dp workflow skills.",
            }
        )
    return changes


def _adoption_conflicts(instruction_findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflict_codes = {
        "instruction_conflicting_session_completion",
        "instruction_unsafe_bypass_guidance",
        "instruction_nested_override_risk",
        "instruction_skill_contradicts_agents",
        "instruction_hook_contradicts_agents",
    }
    return [finding for finding in instruction_findings if finding["code"] in conflict_codes]


def _adoption_hints(classification: str, signals: dict[str, Any]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    if classification in {"not_adopted", "legacy_dp", "partial_spec80", "current_spec80"}:
        hints.append(hint_payload("DP-HINT-ADOPTION-AVAILABLE"))
    if classification in {"legacy_dp", "partial_spec80"} or (
        classification != "current_spec81" and signals["old_command_docs"]
    ):
        hints.append(hint_payload("DP-HINT-MIGRATION-LEGACY-ARTIFACTS"))
    if not signals["has_agents_md"]:
        hints.append(hint_payload("DP-HINT-ADOPTION-PLAN-REQUIRED"))
    return hints


def _adoption_next_actions(classification: str) -> list[dict[str, str]]:
    if classification == "current_spec81":
        return [
            next_action(
                "audit_instructions",
                "dp instructions audit --json",
                "Confirm local instruction guidance remains consistent.",
            )
        ]
    return [
        next_action(
            "plan_adoption",
            "dp adopt plan --write --json",
            "Write an additive migration/adoption plan before applying changes.",
        )
    ]


def _has_spec81_surface(root: Path) -> bool:
    return all(
        (root / path).exists()
        for path in (
            "docs/reference/agent-response-contract.md",
            "docs/reference/toolcards.md",
            "docs/reference/hint-codes.md",
        )
    )


def _missing_spec80_structures(root: Path) -> list[str]:
    return [
        path
        for path in ("docs/goals", "docs/evidence", "docs/loops", "docs/campaigns", ".dp/goals")
        if not (root / path).exists()
    ]


def _missing_spec81_structures(root: Path) -> list[str]:
    return [
        path
        for path in (
            "docs/reference/agent-response-contract.md",
            "docs/reference/toolcards.md",
            "docs/reference/hint-codes.md",
            ".agents/skills",
        )
        if not (root / path).exists()
    ]


def _docs_with_old_commands(root: Path) -> list[str]:
    matches: list[str] = []
    for path in root.rglob("*.md"):
        if any(part in {".git", ".venv", ".uv-cache"} for part in path.parts):
            continue
        relative = path.relative_to(root)
        if (
            len(relative.parts) >= 2
            and relative.parts[0] == "tests"
            and relative.parts[1] == "fixtures"
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        if "bd sync" in text:
            matches.append(relative.as_posix())
    return matches[:20]


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""


def _today_slug() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def _plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        f"# {plan['id']}",
        "",
        f"Status: {plan['status']}",
        f"Source classification: {plan['source_state']['classification']}",
        "",
        "## Changes",
        "",
    ]
    for change in plan["changes"]:
        lines.append(
            f"- `{change['id']}` {change['kind']} `{change['path']}` ({change['mode']}): "
            f"{change['reason']}"
        )
    lines.extend(["", "## Conflicts", ""])
    if plan["conflicts"]:
        for conflict in plan["conflicts"]:
            lines.append(f"- `{conflict['code']}` `{conflict['path']}`: {conflict['summary']}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Verification", ""])
    lines.extend(f"- `{command}`" for command in plan["verification"])
    return "\n".join(lines) + "\n"


def _adoption_error(code: str, message: str) -> AdoptionCommandResult:
    return AdoptionCommandResult(
        payload={
            "schema_version": APPLY_SCHEMA_VERSION,
            "ok": False,
            "status": "invalid",
            "error": {"code": code, "message": message},
        },
        exit_code=2,
    )
