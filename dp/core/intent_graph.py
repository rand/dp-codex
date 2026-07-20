from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from dp.core.goal_lint import collect_intent_findings
from dp.core.goal_state import (
    DEFAULT_GOAL_EVENT_LOG,
    reconstruct_goal_state,
)

GRAPH_AUDIT_SCHEMA_VERSION = "dp.graph.audit.v1"
GOALS_DIRECTORY = Path("docs/goals")
DEFEATER_FINDING_CODES = frozenset({"missing_intent_defeaters", "invalid_intent_defeater"})


@dataclass(frozen=True)
class GraphAuditResult:
    payload: dict[str, Any]
    exit_code: int


def audit_graph(repo_root: Path | None = None) -> GraphAuditResult:
    """Walk docs/goals/*.json and report intent-graph drift without gating.

    The audit reports missing or partial intent blocks, empty defeaters,
    parent links to nonexistent goals, stale parent snapshots, and
    receipts-since-last-outcome-contact per goal. It always exits 0.
    """
    root = (repo_root or Path.cwd()).resolve()
    goals_dir = root / GOALS_DIRECTORY
    event_log = root / DEFAULT_GOAL_EVENT_LOG
    goal_paths = sorted(goals_dir.glob("*.json")) if goals_dir.exists() else []

    contracts: list[tuple[Path, dict[str, Any] | None]] = []
    for path in goal_paths:
        contracts.append((path, _read_goal_contract(path)))

    digest_by_goal_id: dict[str, str] = {}
    for path, contract in contracts:
        if contract is None:
            continue
        goal_id = _text(contract.get("id"))
        if goal_id is not None and goal_id not in digest_by_goal_id:
            digest_by_goal_id[goal_id] = _file_sha256(path)

    goals: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for path, contract in contracts:
        entry, entry_findings = _audit_goal(
            path=path,
            contract=contract,
            root=root,
            event_log=event_log,
            digest_by_goal_id=digest_by_goal_id,
        )
        goals.append(entry)
        findings.extend(entry_findings)

    payload = {
        "schema_version": GRAPH_AUDIT_SCHEMA_VERSION,
        "ok": True,
        "command": "graph.audit",
        "root": root.as_posix(),
        "goals_directory": GOALS_DIRECTORY.as_posix(),
        "goals": goals,
        "findings": findings,
        "summary": {
            "goals": len(goals),
            "findings": len(findings),
            "with_intent": sum(1 for goal in goals if goal["intent_status"] == "ok"),
        },
        "message": "Graph audit reports drift; it does not gate. Exit code is always 0.",
    }
    return GraphAuditResult(payload=payload, exit_code=0)


def goal_file_digest(path: Path) -> str:
    """Content digest used for intent.parent.parent_snapshot staleness checks."""
    return _file_sha256(path)


def _audit_goal(
    *,
    path: Path,
    contract: dict[str, Any] | None,
    root: Path,
    event_log: Path,
    digest_by_goal_id: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rel_path = _relative_path(path, root)
    if contract is None:
        finding = _finding(
            "malformed_goal",
            goal_id=None,
            path=rel_path,
            message="Goal file is not a JSON object and cannot be audited.",
        )
        entry: dict[str, Any] = {
            "goal_id": None,
            "path": rel_path,
            "intent_status": "unreadable",
            "findings": [finding["code"]],
            "receipts_since_last_outcome_contact": None,
            "last_outcome_class": None,
            "parent": None,
        }
        return entry, [finding]

    goal_id = _text(contract.get("id"))
    findings: list[dict[str, Any]] = []
    intent = contract.get("intent")
    intent_status = "ok"

    if not isinstance(intent, dict):
        intent_status = "missing"
        findings.append(
            _finding(
                "missing_intent",
                goal_id=goal_id,
                path=rel_path,
                message="Goal has no intent block; work cannot show what it serves.",
            )
        )
    else:
        lint_findings = collect_intent_findings(contract, repo_root=root, required=True)
        defeater_codes = sorted(
            {item.code for item in lint_findings if item.code in DEFEATER_FINDING_CODES}
        )
        other_codes = sorted(
            {item.code for item in lint_findings if item.code not in DEFEATER_FINDING_CODES}
        )
        if defeater_codes:
            intent_status = "partial"
            findings.append(
                _finding(
                    "empty_defeaters",
                    goal_id=goal_id,
                    path=rel_path,
                    message=(
                        "Goal enumerates no defeaters; an evidence-only goal tree "
                        "is an advocacy document."
                    ),
                )
            )
        if other_codes:
            intent_status = "partial"
            findings.append(
                _finding(
                    "partial_intent",
                    goal_id=goal_id,
                    path=rel_path,
                    message="Intent block is present but incomplete.",
                    detail=other_codes,
                )
            )
        findings.extend(
            _audit_parent_link(
                intent=intent,
                goal_id=goal_id,
                rel_path=rel_path,
                digest_by_goal_id=digest_by_goal_id,
            )
        )

    receipts, last_outcome_class = _outcome_counters(
        goal_id=goal_id,
        path=path,
        event_log=event_log,
    )
    goal_entry: dict[str, Any] = {
        "goal_id": goal_id,
        "path": rel_path,
        "intent_status": intent_status,
        "findings": [finding["code"] for finding in findings],
        "receipts_since_last_outcome_contact": receipts,
        "last_outcome_class": last_outcome_class,
        "parent": _parent_goal_id(intent),
    }
    return goal_entry, findings


def _audit_parent_link(
    *,
    intent: dict[str, Any],
    goal_id: str | None,
    rel_path: str,
    digest_by_goal_id: dict[str, str],
) -> list[dict[str, Any]]:
    parent = intent.get("parent")
    if not isinstance(parent, dict):
        return []
    parent_goal = _text(parent.get("goal"))
    if parent_goal is None:
        return []

    findings: list[dict[str, Any]] = []
    parent_digest = digest_by_goal_id.get(parent_goal)
    if parent_digest is None:
        findings.append(
            _finding(
                "unknown_parent_goal",
                goal_id=goal_id,
                path=rel_path,
                message=f"Intent parent goal has no goal file in docs/goals: {parent_goal}",
            )
        )
        return findings

    snapshot = _text(parent.get("parent_snapshot"))
    if snapshot is not None and snapshot != parent_digest:
        findings.append(
            _finding(
                "stale_parent_snapshot",
                goal_id=goal_id,
                path=rel_path,
                message=(
                    f"Parent goal {parent_goal} changed since this child's intent "
                    "was derived; re-examine the contribution claim."
                ),
            )
        )
    return findings


def _outcome_counters(
    *,
    goal_id: str | None,
    path: Path,
    event_log: Path,
) -> tuple[int | None, str | None]:
    if goal_id is None:
        return None, None
    state = reconstruct_goal_state(
        goal_id=goal_id,
        goal_path=path,
        event_log=event_log,
    )
    last_outcome_class: str | None = None
    if isinstance(state.last_outcome, dict):
        last_outcome_class = _text(state.last_outcome.get("class"))
    return state.receipts_since_last_outcome_contact, last_outcome_class


def _read_goal_contract(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _finding(
    code: str,
    *,
    goal_id: str | None,
    path: str,
    message: str,
    detail: list[str] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "code": code,
        "goal_id": goal_id,
        "path": path,
        "message": message,
    }
    if detail is not None:
        finding["detail"] = detail
    return finding


def _parent_goal_id(intent: Any) -> str | None:
    if not isinstance(intent, dict):
        return None
    parent = intent.get("parent")
    if not isinstance(parent, dict):
        return None
    return _text(parent.get("goal"))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
