from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .adr import list_adrs
from .spec_parser import parse_spec_ids


@dataclass(frozen=True)
class ProgressSnapshot:
    timestamp_utc: str
    dirty_files: int
    spec_count: int
    adr_count: int
    ready_issue_count: int | None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "dirty_files": self.dirty_files,
            "spec_count": self.spec_count,
            "adr_count": self.adr_count,
            "ready_issue_count": self.ready_issue_count,
        }


@dataclass(frozen=True)
class WatchTrigger:
    name: str
    triggered: bool
    reason: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "triggered": self.triggered,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AgentBootstrap:
    summary: str
    triggered_checks: tuple[str, ...]
    next_steps: tuple[str, ...]

    def to_dict(self) -> dict[str, str | list[str]]:
        return {
            "summary": self.summary,
            "triggered_checks": list(self.triggered_checks),
            "next_steps": list(self.next_steps),
        }


@dataclass(frozen=True)
class ProgressReport:
    snapshot: ProgressSnapshot
    triggers: tuple[WatchTrigger, ...]

    def to_dict(self) -> dict[str, object]:
        bootstrap = _build_agent_bootstrap(self.snapshot, self.triggers)
        return {
            "snapshot": self.snapshot.to_dict(),
            "triggers": [trigger.to_dict() for trigger in self.triggers],
            "agent_bootstrap": bootstrap.to_dict(),
        }


def collect_progress_snapshot(repo_root: Path) -> ProgressSnapshot:
    spec_directory = repo_root / "docs/specs"
    spec_files = sorted(spec_directory.glob("**/*.md")) if spec_directory.exists() else []
    spec_count = len(parse_spec_ids(spec_files))
    adr_count = len(list_adrs(repo_root / "docs/adr"))

    return ProgressSnapshot(
        timestamp_utc=_utc_timestamp(),
        dirty_files=_count_dirty_files(repo_root),
        spec_count=spec_count,
        adr_count=adr_count,
        ready_issue_count=_count_ready_issues(repo_root),
    )


def evaluate_watch_triggers(
    current: ProgressSnapshot,
    previous: ProgressSnapshot | None,
) -> tuple[WatchTrigger, ...]:
    triggers: list[WatchTrigger] = []

    triggers.append(
        WatchTrigger(
            name="working-tree-dirty",
            triggered=current.dirty_files > 0,
            reason=f"dirty_files={current.dirty_files}",
        )
    )

    if previous is None:
        triggers.append(
            WatchTrigger(
                name="ready-issue-growth",
                triggered=False,
                reason="no previous snapshot available",
            )
        )
    elif current.ready_issue_count is None or previous.ready_issue_count is None:
        triggers.append(
            WatchTrigger(
                name="ready-issue-growth",
                triggered=False,
                reason="ready issue count unavailable in one or both snapshots",
            )
        )
    else:
        delta = current.ready_issue_count - previous.ready_issue_count
        triggers.append(
            WatchTrigger(
                name="ready-issue-growth",
                triggered=delta > 0,
                reason=f"ready_issue_delta={delta}",
            )
        )

    if previous is None:
        triggers.append(
            WatchTrigger(
                name="spec-count-change",
                triggered=False,
                reason="no previous snapshot available",
            )
        )
    else:
        delta = current.spec_count - previous.spec_count
        triggers.append(
            WatchTrigger(
                name="spec-count-change",
                triggered=delta != 0,
                reason=f"spec_count_delta={delta}",
            )
        )

    return tuple(triggers)


def write_progress_report(report: ProgressReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.snapshot.timestamp_utc.replace(":", "").replace("-", "")
    stem = f"progress-{stamp}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"

    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, md_path


def load_snapshot(path: Path) -> ProgressSnapshot:
    payload = json.loads(path.read_text(encoding="utf-8"))
    snapshot_raw = payload.get("snapshot", payload)
    if not isinstance(snapshot_raw, dict):
        raise ValueError("Invalid snapshot payload: snapshot object missing.")

    try:
        return ProgressSnapshot(
            timestamp_utc=str(snapshot_raw["timestamp_utc"]),
            dirty_files=int(snapshot_raw["dirty_files"]),
            spec_count=int(snapshot_raw["spec_count"]),
            adr_count=int(snapshot_raw["adr_count"]),
            ready_issue_count=(
                int(snapshot_raw["ready_issue_count"])
                if snapshot_raw.get("ready_issue_count") is not None
                else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid snapshot payload: missing or invalid required fields.") from exc


def _render_markdown(report: ProgressReport) -> str:
    bootstrap = _build_agent_bootstrap(report.snapshot, report.triggers)

    lines = [
        "# Progress Snapshot",
        "",
        f"- Timestamp (UTC): `{report.snapshot.timestamp_utc}`",
        f"- Dirty files: `{report.snapshot.dirty_files}`",
        f"- Spec count: `{report.snapshot.spec_count}`",
        f"- ADR count: `{report.snapshot.adr_count}`",
        f"- Ready issue count: `{report.snapshot.ready_issue_count}`",
        "",
        "## Watch Triggers",
        "",
    ]

    if not report.triggers:
        lines.append("- none")
    else:
        for trigger in report.triggers:
            state = "triggered" if trigger.triggered else "not-triggered"
            lines.append(f"- `{trigger.name}`: `{state}` ({trigger.reason})")

    lines.extend(
        [
            "",
            "## Agent Bootstrap",
            "",
            f"- Summary: {bootstrap.summary}",
            f"- Triggered checks: {', '.join(bootstrap.triggered_checks) or 'none'}",
            "",
            "### Next Steps",
            "",
        ]
    )
    for step in bootstrap.next_steps:
        lines.append(f"1. `{step}`")

    lines.append("")
    return "\n".join(lines)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _count_dirty_files(repo_root: Path) -> int:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        check=False,
        cwd=repo_root,
        text=True,
    )
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def _count_ready_issues(repo_root: Path) -> int | None:
    result = subprocess.run(
        ["bd", "ready", "--json"],
        capture_output=True,
        check=False,
        cwd=repo_root,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, list):
        return len(payload)
    return None


def _build_agent_bootstrap(
    snapshot: ProgressSnapshot,
    triggers: tuple[WatchTrigger, ...],
) -> AgentBootstrap:
    triggered_checks = [trigger.name for trigger in triggers if trigger.triggered]
    summary = (
        f"dirty_files={snapshot.dirty_files}, "
        f"ready_issues={snapshot.ready_issue_count}, "
        f"specs={snapshot.spec_count}, adrs={snapshot.adr_count}"
    )
    next_steps = [
        "bd ready",
        "make check",
        "uv run dp review --json",
    ]
    if triggered_checks:
        next_steps.insert(0, "Inspect triggered watch checks and resolve blockers")

    return AgentBootstrap(
        summary=summary,
        triggered_checks=tuple(triggered_checks),
        next_steps=tuple(next_steps),
    )
