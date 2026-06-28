from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.agent_response import next_action
from dp.core.hints import hint_payload

HOOKS_SCHEMA_VERSION = "dp.hooks.v1"


@dataclass(frozen=True)
class HooksCommandResult:
    payload: dict[str, Any]
    exit_code: int


def audit_hooks(repo_root: Path | None = None) -> HooksCommandResult:
    root = (repo_root or Path.cwd()).resolve()
    hooks = _discover_hooks(root)
    findings: list[dict[str, str]] = []
    for hook in hooks:
        findings.extend(_audit_hook(root, hook))
    payload = {
        "schema_version": HOOKS_SCHEMA_VERSION,
        "ok": True,
        "command": "hooks.audit",
        "hooks": [_hook_summary(root, hook) for hook in hooks],
        "findings": findings,
        "hints": _hook_hints(findings),
        "next_actions": [
            next_action("doctor_hooks", "dp hooks doctor --json", "Summarize hook health."),
            next_action(
                "scaffold_codex_hooks",
                "dp hooks scaffold --target codex --json",
                "Preview conservative Codex hook templates.",
            ),
        ],
    }
    return HooksCommandResult(payload=payload, exit_code=0)


def doctor_hooks(repo_root: Path | None = None) -> HooksCommandResult:
    audit = audit_hooks(repo_root)
    findings = audit.payload["findings"]
    blocking = [
        finding
        for finding in findings
        if finding["code"] in {"hook_calls_llm"}
    ]
    payload = {
        "schema_version": HOOKS_SCHEMA_VERSION,
        "ok": not blocking,
        "command": "hooks.doctor",
        "status": "ok" if not blocking else "warning",
        "summary": {
            "hooks": len(audit.payload["hooks"]),
            "findings": len(findings),
            "blocking": len(blocking),
        },
        "findings": findings,
        "hints": audit.payload["hints"],
    }
    return HooksCommandResult(payload=payload, exit_code=0 if not blocking else 1)


def scaffold_hooks(
    repo_root: Path | None = None,
    *,
    target: str,
    write: bool = False,
) -> HooksCommandResult:
    if target not in {"git", "codex"}:
        return _hooks_error("unsupported_target", "Hook target must be git or codex.")
    root = (repo_root or Path.cwd()).resolve()
    templates = _hook_templates(target)
    artifacts: list[dict[str, Any]] = []
    if write:
        template_root = root / ".dp/hook-templates" / target
        template_root.mkdir(parents=True, exist_ok=True)
        for name, body in templates.items():
            path = template_root / name
            path.write_text(body, encoding="utf-8")
            artifacts.append({"kind": "hook_template", "path": path.relative_to(root).as_posix()})
    payload = {
        "schema_version": HOOKS_SCHEMA_VERSION,
        "ok": True,
        "command": "hooks.scaffold",
        "target": target,
        "write": write,
        "installed": False,
        "templates": [{"name": name, "content": body} for name, body in templates.items()],
        "artifacts": artifacts,
        "hints": [hint_payload("DP-HINT-HOOKS-UNTRUSTED")],
        "next_actions": [
            next_action("audit_hooks", "dp hooks audit --json", "Audit hooks before installing.")
        ],
    }
    return HooksCommandResult(payload=payload, exit_code=0)


def _discover_hooks(root: Path) -> list[Path]:
    paths: list[Path] = []
    for candidate in (root / ".codex/hooks.json", root / ".codex/config.toml"):
        if candidate.is_file():
            paths.append(candidate)
    hooks_dir = root / "hooks"
    if hooks_dir.exists():
        paths.extend(path for path in hooks_dir.rglob("*") if path.is_file())
    git_hooks = root / ".git/hooks"
    if git_hooks.exists():
        paths.extend(
            path
            for path in git_hooks.iterdir()
            if path.is_file() and not path.name.endswith(".sample")
        )
    return sorted(set(paths))


def _audit_hook(root: Path, path: Path) -> list[dict[str, str]]:
    text = _read_text(path)
    rel = path.relative_to(root).as_posix()
    lowered = text.lower()
    findings: list[dict[str, str]] = []
    if any(term in lowered for term in ("openai", "anthropic", "llm", "chatgpt", "claude")):
        findings.append(
            _finding(
                "hook_calls_llm",
                "warning",
                rel,
                "Hook appears to call an LLM or model provider.",
                "DP-HINT-HOOKS-UNTRUSTED",
            )
        )
    if any(term in lowered for term in ("curl ", "wget ", "http://", "https://")):
        findings.append(
            _finding(
                "hook_calls_network",
                "warning",
                rel,
                "Hook appears to call the network.",
                "DP-HINT-HOOKS-UNTRUSTED",
            )
        )
    if any(term in lowered for term in ("git push --no-verify", "dp_bypass_enforcement")):
        findings.append(
            _finding(
                "hook_bypass_path",
                "warning",
                rel,
                "Hook references a bypass path.",
                "DP-HINT-HOOK-BYPASSED",
            )
        )
    if path.name == "hooks.json":
        _audit_codex_hook_json(rel, text, findings)
    elif "timeout" not in lowered and "pre-commit" in rel:
        findings.append(
            _finding(
                "hook_missing_timeout",
                "warning",
                rel,
                "Hook does not mention an explicit timeout.",
                "DP-HINT-HOOKS-UNTRUSTED",
            )
        )
    if "../" in text:
        findings.append(
            _finding(
                "hook_relative_path_risk",
                "warning",
                rel,
                "Hook contains parent-relative paths that may break from subdirectories.",
                "DP-HINT-HOOKS-UNTRUSTED",
            )
        )
    return findings


def _audit_codex_hook_json(
    rel: str,
    text: str,
    findings: list[dict[str, str]],
) -> None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        findings.append(
            _finding(
                "hook_config_malformed",
                "warning",
                rel,
                "Codex hook configuration is not valid JSON.",
                "DP-HINT-HOOKS-UNTRUSTED",
            )
        )
        return
    serialized = json.dumps(payload).lower()
    if "timeout" not in serialized and "timeout_ms" not in serialized:
        findings.append(
            _finding(
                "hook_missing_timeout",
                "warning",
                rel,
                "Codex hook configuration does not declare explicit timeouts.",
                "DP-HINT-HOOKS-UNTRUSTED",
            )
        )


def _hook_summary(root: Path, path: Path) -> dict[str, Any]:
    text = _read_text(path)
    rel = path.relative_to(root).as_posix()
    if rel.startswith(".git/hooks/"):
        kind = "git"
    elif rel.startswith(".codex/"):
        kind = "codex"
    else:
        kind = "project"
    return {
        "path": rel,
        "kind": kind,
        "size_bytes": len(text.encode("utf-8")),
        "deterministic_hint": not any(
            term in text.lower() for term in ("openai", "anthropic", "llm")
        ),
    }


def _hook_templates(target: str) -> dict[str, str]:
    if target == "git":
        return {
            "pre-commit": (
                "#!/bin/sh\n"
                "set -eu\n"
                "timeout 120 dp enforce pre-commit --policy dp-policy.json --json\n"
            ),
            "pre-push": (
                "#!/bin/sh\n"
                "set -eu\n"
                "timeout 180 dp enforce pre-push --policy dp-policy.json --json\n"
            ),
        }
    return {
        "hooks.json": json.dumps(
            {
                "SessionStart": {
                    "command": "dp agent bootstrap --json --detail brief",
                    "timeout_ms": 5000,
                    "mode": "suggest",
                },
                "PreCompact": {
                    "command": "dp agent bootstrap --json --detail brief",
                    "timeout_ms": 5000,
                    "mode": "suggest",
                },
                "Stop": {
                    "command": "dp doctor --json",
                    "timeout_ms": 5000,
                    "mode": "suggest",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    }


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


def _hook_hints(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    if not findings:
        return []
    seen: set[str] = set()
    hints = []
    for finding in findings:
        hint_code = finding["hint_code"]
        if hint_code not in seen:
            seen.add(hint_code)
            hints.append(hint_payload(hint_code))
    return hints


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""


def _hooks_error(code: str, message: str) -> HooksCommandResult:
    return HooksCommandResult(
        payload={
            "schema_version": HOOKS_SCHEMA_VERSION,
            "ok": False,
            "error": {"code": code, "message": message},
        },
        exit_code=2,
    )
