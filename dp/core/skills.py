from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.agent_response import next_action
from dp.core.hints import hint_payload

SKILLS_SCHEMA_VERSION = "dp.skills.v1"
SKILL_NAMES = (
    "dp-agent-bootstrap",
    "dp-campaign-control",
    "dp-goal-lifecycle",
    "dp-evidence-repair",
    "dp-failure-recovery",
    "dp-adoption-migration",
    "dp-instruction-governance",
    "dp-session-handoff",
    "dp-hook-triage",
)


@dataclass(frozen=True)
class SkillsCommandResult:
    payload: dict[str, Any]
    exit_code: int


def scaffold_skills(
    repo_root: Path | None = None,
    *,
    target: str,
) -> SkillsCommandResult:
    if target != "repo":
        return _skills_error("unsupported_target", "Only --target repo is supported.")
    root = (repo_root or Path.cwd()).resolve()
    skills_root = root / ".agents/skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for name, body in skill_templates().items():
        skill_dir = skills_root / name
        skill_path = skill_dir / "SKILL.md"
        if skill_path.exists():
            skipped.append({"name": name, "path": skill_path.relative_to(root).as_posix()})
            continue
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(body, encoding="utf-8")
        written.append({"name": name, "path": skill_path.relative_to(root).as_posix()})

    payload = {
        "schema_version": SKILLS_SCHEMA_VERSION,
        "ok": True,
        "command": "skills.scaffold",
        "target": target,
        "written": written,
        "skipped": skipped,
        "hints": [hint_payload("DP-HINT-SKILL-SUGGESTED")],
        "next_actions": [
            next_action("audit_skills", "dp skills audit --json", "Verify skill compactness.")
        ],
    }
    return SkillsCommandResult(payload=payload, exit_code=0)


def lint_skills(repo_root: Path | None = None) -> SkillsCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    skills = _discover_skills(root)
    findings: list[dict[str, Any]] = []
    for skill in skills:
        findings.extend(_lint_skill(root, skill))
    payload = {
        "schema_version": SKILLS_SCHEMA_VERSION,
        "ok": not any(finding["severity"] == "error" for finding in findings),
        "command": "skills.lint",
        "skills": [_skill_summary(root, path) for path in skills],
        "findings": findings,
        "hints": _skill_hints(findings),
    }
    return SkillsCommandResult(payload=payload, exit_code=0 if payload["ok"] else 1)


def audit_skills(repo_root: Path | None = None) -> SkillsCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    lint_result = lint_skills(root)
    skills = lint_result.payload["skills"]
    findings = list(lint_result.payload["findings"])
    present = {skill["name"] for skill in skills}
    missing = [name for name in SKILL_NAMES if name not in present]
    for name in missing:
        findings.append(
            {
                "code": "skill_missing",
                "severity": "warning",
                "path": f".agents/skills/{name}/SKILL.md",
                "summary": "Expected SPEC-81 repo skill is missing.",
                "hint_code": "DP-HINT-SKILL-SUGGESTED",
            }
        )
    payload = {
        "schema_version": SKILLS_SCHEMA_VERSION,
        "ok": True,
        "command": "skills.audit",
        "skills": skills,
        "missing": missing,
        "findings": findings,
        "hints": _skill_hints(findings),
        "next_actions": [
            next_action(
                "scaffold_missing",
                "dp skills scaffold --target repo --json",
                "Create missing focused dp skills without overwriting existing files.",
            )
        ],
    }
    return SkillsCommandResult(payload=payload, exit_code=0)


def eval_skills() -> SkillsCommandResult:
    fixtures = [
        ("I just opened this repo, what should I do first?", "dp-agent-bootstrap"),
        ("Use the next campaign goal.", "dp-campaign-control"),
        ("Evidence failed, repair it.", "dp-evidence-repair"),
        ("Retry this failed evidence check.", "dp-evidence-repair"),
        ("Recover this failing gate.", "dp-failure-recovery"),
        ("Recover this failed gate.", "dp-failure-recovery"),
        ("Rescue this blocked or stranded goal.", "dp-failure-recovery"),
        ("Upgrade this old dp project.", "dp-adoption-migration"),
        ("Do not overwrite our AGENTS.md.", "dp-instruction-governance"),
        ("Hook failed.", "dp-hook-triage"),
        ("End this session cleanly.", "dp-session-handoff"),
    ]
    results = []
    for prompt, expected in fixtures:
        actual = _match_skill(prompt)
        results.append(
            {
                "prompt": prompt,
                "expected": expected,
                "actual": actual,
                "ok": actual == expected,
            }
        )
    passed = sum(1 for item in results if item["ok"])
    payload = {
        "schema_version": SKILLS_SCHEMA_VERSION,
        "ok": passed == len(results),
        "command": "skills.eval",
        "results": results,
        "metrics": {
            "fixtures": len(results),
            "passed": passed,
            "skill_trigger_precision": passed / len(results),
            "skill_trigger_recall": passed / len(results),
        },
    }
    return SkillsCommandResult(payload=payload, exit_code=0 if payload["ok"] else 1)


def skill_templates() -> dict[str, str]:
    return {
        "dp-agent-bootstrap": _skill(
            "dp-agent-bootstrap",
            (
                "Orient in a dp-codex-aware repo; trigger on first command, opened repo, "
                "bootstrap, where to start."
            ),
            "Run `dp agent bootstrap --json --detail brief` first.",
            "Use when entering or resuming a repository.",
        ),
        "dp-campaign-control": _skill(
            "dp-campaign-control",
            "Claim or recover campaign work; trigger on campaign, next goal, loop, SPEC-80.",
            "Run `dp campaign status <campaign.json> --json --detail brief` or `dp loop next ...`.",
            "Use for one bounded campaign goal at a time.",
        ),
        "dp-goal-lifecycle": _skill(
            "dp-goal-lifecycle",
            "Manage goal state; trigger on start, block, release, verify, lease.",
            "Run `dp goal status <goal.json> --json --detail brief` before changing state.",
            "Use for GoalContract lifecycle transitions.",
        ),
        "dp-evidence-repair": _skill(
            "dp-evidence-repair",
            "Repair evidence failures; trigger on failed check, stale run, missing validator.",
            "Run `dp explain DP-HINT-EVIDENCE-FAILED --json` and inspect full evidence detail.",
            "Use when deterministic evidence blocks completion.",
        ),
        "dp-failure-recovery": _failure_recovery_skill(),
        "dp-adoption-migration": _skill(
            "dp-adoption-migration",
            "Adopt or migrate old dp projects; trigger on upgrade, legacy dp, migration.",
            "Run `dp adopt inspect --json` before planning or applying changes.",
            "Use to plan additive adoption without erasing history.",
        ),
        "dp-instruction-governance": _skill(
            "dp-instruction-governance",
            "Respect and audit instructions; trigger on AGENTS.md, override, local law.",
            "Run `dp instructions inspect --json` and then `dp instructions audit --json`.",
            "Use before editing project instruction files.",
        ),
        "dp-session-handoff": _skill(
            "dp-session-handoff",
            "End or resume a session; trigger on handoff, compact, stop, session end.",
            "Run `dp agent bootstrap --json --detail brief` and record current dp status.",
            "Use before context compaction or final session closeout.",
        ),
        "dp-hook-triage": _skill(
            "dp-hook-triage",
            "Audit hook failures; trigger on hook failed, Codex hook, git hook.",
            "Run `dp hooks audit --json` before changing hook files.",
            "Use for deterministic local hook triage only.",
        ),
    }


def _skill(name: str, description: str, first_command: str, when: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        f"# {name}\n\n"
        "Respect `AGENTS.md` and any nested `AGENTS.md` before using this skill.\n\n"
        f"When to use: {when}\n\n"
        "When not to use: unrelated repositories that have not opted into dp-codex.\n\n"
        f"First command: {first_command}\n\n"
        "Keep work scoped, prefer compact JSON detail first, and expand only when needed.\n"
    )


# @trace SPEC-81.02
def _failure_recovery_skill() -> str:
    return (
        "---\n"
        "name: dp-failure-recovery\n"
        "description: Diagnose and recover a failing gate, blocked or stranded dp goal, broken "
        "workflow, rescue request, repeated non-evidence retry, or uncertain stop condition.\n"
        "---\n\n"
        "# DP Failure Recovery\n\n"
        "Respect `AGENTS.md`, nested instructions, the active GoalContract, and existing claims "
        "before acting. A red gate blocks completion, not diagnosis or authorized repair. "
        "Proportional verification decides done; verification volume does not.\n\n"
        "## Capture\n\n"
        "Record the exact command, exit code, failed check, branch/HEAD, worktree state, "
        "applicable allowed paths, attempt budget, and failed receipt. Preserve prior evidence.\n\n"
        "## Classify in order\n\n"
        "1. `invalid_execution`: invocation, environment, cache, lease, worktree, or tool state "
        "produced no trustworthy verdict. Repair only non-semantic execution state and rerun the "
        "same command.\n"
        "2. `repairable_failure`: a smallest safe repair is authorized by local law and the "
        "active contract.\n"
        "3. `independent_repair`: the defect is non-semantic but outside the active contract, and "
        "another owner or repair goal can fix it without a human semantic or authority decision.\n"
        "4. `true_blocker`: a new public behavior, schema, exit code, DoD, authority, external "
        "dependency, validator, unsafe scope, or exhausted attempt budget is required.\n\n"
        "## Repair\n\n"
        "For `repairable_failure`, state the hypothesis, make the smallest coherent reversible "
        "repair inside allowed paths, rerun the exact failed check, then run required gates. Do "
        "not weaken a test, validator, contract, fixture, or evidence assertion. Do not repeat an "
        "unchanged action unless relevant state or the hypothesis changed.\n\n"
        "For `independent_repair`, preserve the failure and route a bounded follow-up without "
        "expanding the active goal. For `true_blocker`, use a supported GoalContract blocker route "
        "and keep dp, Beads, reports, and Git state truthful.\n\n"
        "## Consult\n\n"
        "Use read-only investigator, specialist, or adversarial agents for independent diagnostic "
        "threads, domain risk, context pressure, or a failed hypothesis when orchestration is "
        "available and allowed. Give each helper a question, read/write scope, forbidden actions, "
        "expected output, and stop condition.\n\n"
        "One writer owns one worktree. Writing helpers require isolated worktrees and disjoint "
        "paths. The primary agent owns lifecycle changes, tracker truth, adopted edits, and "
        "verification. External agent output is advisory, cannot establish completion, and must "
        "not receive repository material without applicable authorization. Unavailable "
        "consultation is not a blocker for otherwise ready work.\n\n"
        "## Stop\n\n"
        "Stop the affected goal only when no safe discriminating repair remains, required "
        "authority is missing, the contract requires an independent repair, or its attempt budget "
        "is exhausted. Record the exact reason and next action. Never turn a consultation result "
        "or narration into evidence.\n"
    )


def _discover_skills(root: Path) -> list[Path]:
    skills_root = root / ".agents/skills"
    if not skills_root.exists():
        return []
    return sorted(path for path in skills_root.glob("*/SKILL.md") if path.is_file())


def _lint_skill(root: Path, path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    rel = path.relative_to(root).as_posix()
    metadata = _frontmatter(text)
    findings: list[dict[str, Any]] = []
    if not metadata.get("name"):
        findings.append(_finding("skill_missing_name", "error", rel, "Skill lacks name metadata."))
    if not metadata.get("description"):
        findings.append(
            _finding("skill_missing_description", "error", rel, "Skill lacks description metadata.")
        )
    if len(str(metadata.get("description") or "")) > 240:
        findings.append(
            _finding("skill_description_too_long", "warning", rel, "Skill description is long.")
        )
    if len(text) > 5_000:
        findings.append(_finding("skill_body_too_large", "warning", rel, "Skill body is large."))
    lowered = text.lower()
    if "agents.md" not in lowered:
        findings.append(
            _finding(
                "skill_missing_agents_precedence",
                "warning",
                rel,
                "Skill does not explicitly preserve AGENTS.md precedence.",
            )
        )
    if "ignore agents.md" in lowered or "overwrite agents.md" in lowered:
        findings.append(
            _finding(
                "skill_contradicts_agents",
                "error",
                rel,
                "Skill appears to contradict AGENTS.md precedence.",
            )
        )
    return findings


def _skill_summary(root: Path, path: Path) -> dict[str, Any]:
    text = _read_text(path)
    metadata = _frontmatter(text)
    return {
        "name": str(metadata.get("name") or path.parent.name),
        "path": path.relative_to(root).as_posix(),
        "description": str(metadata.get("description") or ""),
        "size_bytes": len(text.encode("utf-8")),
    }


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    metadata: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _match_skill(prompt: str) -> str | None:
    lowered = prompt.lower()
    if any(term in lowered for term in ("opened", "first", "what should i do", "bootstrap")):
        return "dp-agent-bootstrap"
    if any(term in lowered for term in ("evidence", "validator", "failed check")):
        return "dp-evidence-repair"
    if any(term in lowered for term in ("campaign", "next goal", "loop")):
        return "dp-campaign-control"
    if "hook" in lowered:
        return "dp-hook-triage"
    if any(
        term in lowered
        for term in (
            "blocked",
            "stranded",
            "rescue",
            "unblock",
            "retry",
            "failed",
            "failing",
        )
    ):
        return "dp-failure-recovery"
    if any(term in lowered for term in ("upgrade", "old dp", "migrate", "adopt")):
        return "dp-adoption-migration"
    if any(term in lowered for term in ("agents.md", "overwrite", "instructions")):
        return "dp-instruction-governance"
    if any(term in lowered for term in ("end this session", "handoff", "compact", "stop")):
        return "dp-session-handoff"
    return None


def _finding(code: str, severity: str, path: str, summary: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "summary": summary,
        "hint_code": "DP-HINT-SKILL-TRIGGER-AMBIGUOUS"
        if severity == "error"
        else "DP-HINT-SKILL-SUGGESTED",
    }


def _skill_hints(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not findings:
        return []
    seen: set[str] = set()
    hints = []
    for finding in findings:
        hint_code = str(finding.get("hint_code") or "DP-HINT-SKILL-SUGGESTED")
        if hint_code not in seen:
            seen.add(hint_code)
            hints.append(hint_payload(hint_code))
    return hints


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""


def _skills_error(code: str, message: str) -> SkillsCommandResult:
    return SkillsCommandResult(
        payload={
            "schema_version": SKILLS_SCHEMA_VERSION,
            "ok": False,
            "error": {"code": code, "message": message},
        },
        exit_code=2,
    )
