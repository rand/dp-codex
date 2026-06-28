from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.agent_response import next_action
from dp.core.hints import hint_payload

INSPECT_SCHEMA_VERSION = "dp.instructions.inspect.v1"
AUDIT_SCHEMA_VERSION = "dp.instructions.audit.v1"
PLAN_SCHEMA_VERSION = "dp.instructions.plan_update.v1"
OVERSIZED_INSTRUCTION_BYTES = 12_000

IGNORED_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".uv-cache",
        ".venv",
        "__pycache__",
        "node_modules",
    }
)


@dataclass(frozen=True)
class InstructionCommandResult:
    payload: dict[str, Any]
    exit_code: int


@dataclass(frozen=True)
class InstructionFile:
    path: str
    kind: str
    scope: str
    size_bytes: int
    summary: str
    contains_dp_guidance: bool
    precedence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "scope": self.scope,
            "size_bytes": self.size_bytes,
            "summary": self.summary,
            "contains_dp_guidance": self.contains_dp_guidance,
            "precedence": self.precedence,
        }


def inspect_instructions(
    repo_root: Path | None = None,
    *,
    detail: str = "normal",
) -> InstructionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    files = sorted(_discover_instruction_files(root), key=lambda item: (item.precedence, item.path))
    visible_files = files if detail == "full" else files[:40]
    hints = []
    if any(item.kind in {"agents", "agents_override"} for item in files):
        hints.append(hint_payload("DP-HINT-INSTRUCTIONS-FOUND"))
    if len(visible_files) < len(files):
        hints.append(hint_payload("DP-HINT-TOKEN-BUDGET-TRUNCATED"))

    payload: dict[str, Any] = {
        "schema_version": INSPECT_SCHEMA_VERSION,
        "status": "ok",
        "repo_root": root.as_posix(),
        "files": [item.to_dict() for item in visible_files],
        "omitted_count": len(files) - len(visible_files),
        "hints": hints,
        "next_actions": [
            next_action(
                "audit_instructions",
                "dp instructions audit --json",
                "Check local instructions for conflicts and stale dp guidance.",
            )
        ],
    }
    return InstructionCommandResult(payload=payload, exit_code=0)


def audit_instructions(repo_root: Path | None = None) -> InstructionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    inspect_result = inspect_instructions(root, detail="full")
    files = inspect_result.payload["files"]
    findings = _instruction_findings(root, files)
    hints = _hints_for_findings(findings)
    status = "warning" if findings else "ok"
    payload = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": status,
        "ok": True,
        "findings": findings,
        "summary": {
            "files": len(files),
            "warnings": sum(1 for finding in findings if finding["severity"] == "warning"),
            "errors": sum(1 for finding in findings if finding["severity"] == "error"),
        },
        "hints": hints,
        "next_actions": [
            next_action(
                "plan_instruction_update",
                "dp instructions plan-update --json",
                "Preview a minimal dp section without mutating AGENTS.md.",
            )
        ],
    }
    return InstructionCommandResult(payload=payload, exit_code=0)


def plan_instruction_update(repo_root: Path | None = None) -> InstructionCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    inspect_result = inspect_instructions(root, detail="full")
    audit_result = audit_instructions(root)
    files = inspect_result.payload["files"]
    agents_files = [item for item in files if item["kind"] == "agents" and item["scope"] == "repo"]
    target = agents_files[0]["path"] if agents_files else "AGENTS.md"
    contains_bootstrap = any(
        _file_text(root / item["path"]).find("dp agent bootstrap") >= 0 for item in files
    )
    changes: list[dict[str, Any]] = []
    if not contains_bootstrap:
        changes.append(
            {
                "id": "add-dp-agent-workflow",
                "kind": "patch",
                "path": target,
                "mode": "propose",
                "reason": "Add compact bootstrap guidance while preserving existing instructions.",
                "patch_preview": _dp_section_patch(target_exists=bool(agents_files)),
            }
        )

    conflicts = [
        finding
        for finding in audit_result.payload["findings"]
        if finding["code"]
        in {
            "instruction_conflicting_session_completion",
            "instruction_conflicting_test_commands",
            "instruction_unsafe_bypass_guidance",
            "instruction_nested_override_risk",
        }
    ]
    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "status": "planned",
        "would_mutate": False,
        "target": target,
        "changes": changes,
        "conflicts": conflicts,
        "preserve": {
            "existing_agents_md": bool(agents_files),
            "stricter_rules": True,
            "create_agents_override": False,
        },
        "next_actions": [
            next_action(
                "review_plan",
                "Review the patch_preview before editing instruction files.",
                "Project instructions are local law and should not be replaced by dp.",
            )
        ],
        "hints": _hints_for_findings(conflicts),
    }
    return InstructionCommandResult(payload=payload, exit_code=0)


def _discover_instruction_files(root: Path) -> list[InstructionFile]:
    paths: dict[str, Path] = {}
    for pattern in (
        "AGENTS.md",
        "AGENTS.override.md",
        "**/AGENTS.md",
        "**/AGENTS.override.md",
        "README.md",
        "CONTRIBUTING.md",
        "dp-policy.json",
        ".codex/config.toml",
        ".codex/hooks.json",
    ):
        for path in root.glob(pattern):
            if not path.is_file() or _ignored(path.relative_to(root)):
                continue
            paths[path.relative_to(root).as_posix()] = path

    skills_root = root / ".agents/skills"
    if skills_root.exists():
        for path in skills_root.glob("*/SKILL.md"):
            if path.is_file():
                paths[path.relative_to(root).as_posix()] = path

    files = [_instruction_file(root, path) for path in paths.values()]
    return files


def _instruction_file(root: Path, path: Path) -> InstructionFile:
    rel = path.relative_to(root).as_posix()
    text = _file_text(path)
    kind = _kind_for_path(rel)
    scope = _scope_for_path(rel)
    return InstructionFile(
        path=rel,
        kind=kind,
        scope=scope,
        size_bytes=len(text.encode("utf-8")),
        summary=_summary_for_text(text, kind),
        contains_dp_guidance=_contains_dp_guidance(text),
        precedence=_precedence(rel, kind, scope),
    )


def _instruction_findings(root: Path, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    texts = {item["path"]: _file_text(root / item["path"]) for item in files}
    agents_texts = {
        path: text
        for path, text in texts.items()
        if path.endswith("AGENTS.md") or path.endswith("AGENTS.override.md")
    }
    combined_agents = "\n".join(agents_texts.values()).lower()

    if "dp agent bootstrap" not in combined_agents:
        findings.append(
            _finding(
                "instruction_missing_bootstrap",
                "warning",
                "AGENTS.md",
                "No dp agent bootstrap guidance found.",
                "DP-HINT-ADOPTION-AVAILABLE",
            )
        )

    if "do not run tests" in combined_agents and (
        "make test" in combined_agents or "make check" in combined_agents
    ):
        findings.append(
            _finding(
                "instruction_conflicting_test_commands",
                "warning",
                "AGENTS.md",
                "Test guidance appears contradictory.",
                "DP-HINT-INSTRUCTIONS-CONFLICT",
            )
        )

    if ("do not push" in combined_agents or "never push" in combined_agents) and (
        "git push" in combined_agents or "must push" in combined_agents
    ):
        findings.append(
            _finding(
                "instruction_conflicting_session_completion",
                "warning",
                "AGENTS.md",
                "Session completion guidance appears contradictory.",
                "DP-HINT-INSTRUCTIONS-CONFLICT",
            )
        )

    if "git push --no-verify" in combined_agents or "skip all checks" in combined_agents:
        findings.append(
            _finding(
                "instruction_unsafe_bypass_guidance",
                "warning",
                "AGENTS.md",
                "Unsafe bypass guidance was found in local instructions.",
                "DP-HINT-HOOK-BYPASSED",
            )
        )

    dp_guidance_count = sum(
        1
        for item in files
        if item["contains_dp_guidance"] and item["kind"] in {"agents", "agents_override"}
    )
    if dp_guidance_count > 3:
        findings.append(
            _finding(
                "instruction_duplicate_dp_guidance",
                "warning",
                "AGENTS.md",
                "dp guidance appears in several instruction surfaces.",
                "DP-HINT-INSTRUCTIONS-CONFLICT",
            )
        )

    for item in files:
        if (
            item["kind"] in {"agents", "agents_override"}
            and int(item["size_bytes"]) > OVERSIZED_INSTRUCTION_BYTES
        ):
            findings.append(
                _finding(
                    "instruction_file_too_large",
                    "warning",
                    str(item["path"]),
                    "Instruction file exceeds the recommended compact size.",
                    "DP-HINT-INSTRUCTIONS-TOO-LARGE",
                )
            )
        if str(item["path"]).endswith("AGENTS.override.md") and item["scope"] != "repo":
            findings.append(
                _finding(
                    "instruction_nested_override_risk",
                    "warning",
                    str(item["path"]),
                    "Nested override files can unexpectedly supersede local workflow.",
                    "DP-HINT-INSTRUCTIONS-CONFLICT",
                )
            )

    for path, text in texts.items():
        lowered = text.lower()
        if "bd sync" in lowered:
            findings.append(
                _finding(
                    "instruction_stale_old_dp_command",
                    "warning",
                    path,
                    "Stale old dp guidance references bd sync.",
                    "DP-HINT-INSTRUCTIONS-CONFLICT",
                )
            )
        if path.startswith(".agents/skills/") and (
            "ignore agents.md" in lowered or "overwrite agents.md" in lowered
        ):
            findings.append(
                _finding(
                    "instruction_skill_contradicts_agents",
                    "warning",
                    path,
                    "A skill appears to contradict AGENTS.md precedence.",
                    "DP-HINT-SKILL-TRIGGER-AMBIGUOUS",
                )
            )
        if path == ".codex/hooks.json" and (
            "openai" in lowered or "anthropic" in lowered or "llm" in lowered
        ):
            findings.append(
                _finding(
                    "instruction_hook_contradicts_agents",
                    "warning",
                    path,
                    "A hook configuration appears to call an LLM or model provider.",
                    "DP-HINT-HOOKS-UNTRUSTED",
                )
            )

    return findings


def _finding(
    code: str,
    severity: str,
    path: str,
    summary: str,
    hint_code: str,
) -> dict[str, str]:
    return {
        "code": code,
        "severity": severity,
        "path": path,
        "summary": summary,
        "hint_code": hint_code,
    }


def _hints_for_findings(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    hints = []
    for finding in findings:
        hint_code = str(finding.get("hint_code") or "")
        if hint_code and hint_code not in seen:
            seen.add(hint_code)
            hints.append(hint_payload(hint_code))
    return hints


def _dp_section_patch(*, target_exists: bool) -> str:
    prefix = "\n" if target_exists else ""
    return (
        f"{prefix}## dp Agent Workflow\n\n"
        "- Start with `dp agent bootstrap --json --detail brief`.\n"
        "- For campaign work, use `dp loop next ... --claim --emit codex --json`.\n"
        "- Start, block, release, and complete goals through dp lifecycle commands.\n"
        "- Respect this file and any nested AGENTS.md files before dp hints.\n"
        "- Treat dp hints as workflow affordances, not permission to ignore project rules.\n"
        "- Do not mark work complete without evidence.\n"
    )


def _kind_for_path(path: str) -> str:
    if path.endswith("AGENTS.override.md"):
        return "agents_override"
    if path.endswith("AGENTS.md"):
        return "agents"
    if path.endswith("SKILL.md"):
        return "skill"
    if path == ".codex/hooks.json":
        return "hook_config"
    if path == ".codex/config.toml":
        return "codex_config"
    if path == "dp-policy.json":
        return "policy"
    if path.endswith("README.md"):
        return "readme"
    if path.endswith("CONTRIBUTING.md"):
        return "contributing"
    return "fallback"


def _scope_for_path(path: str) -> str:
    if "/" not in path:
        return "repo"
    if path.startswith(".agents/skills/"):
        return "skill"
    if path.startswith(".codex/"):
        return "codex"
    return "nested"


def _precedence(path: str, kind: str, scope: str) -> int:
    if kind == "agents_override" and scope == "repo":
        return 5
    if kind == "agents" and scope == "repo":
        return 10
    if kind == "agents_override":
        return 15
    if kind == "agents":
        return 20
    if kind in {"codex_config", "hook_config"}:
        return 40
    if kind == "skill":
        return 50
    if kind == "policy":
        return 60
    return 80


def _summary_for_text(text: str, kind: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:120]
    if kind == "policy":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return "dp policy configuration"
        mode = payload.get("mode") if isinstance(payload, dict) else None
        return f"dp policy configuration{f' ({mode})' if mode else ''}"
    return f"{kind} guidance"


def _contains_dp_guidance(text: str) -> bool:
    lowered = text.lower()
    return "dp " in lowered or "dp-codex" in lowered or "beads" in lowered


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""


def _ignored(path: Path) -> bool:
    if len(path.parts) >= 2 and path.parts[0] == "tests" and path.parts[1] == "fixtures":
        return True
    return any(part in IGNORED_PARTS for part in path.parts)
