from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Severity = Literal["blocking", "advisory"]
TEXT_SUFFIXES = {".md", ".py", ".pyi", ".sh", ".toml", ".ts", ".tsx", ".yaml", ".yml"}


@dataclass(frozen=True)
class ReviewFinding:
    check_id: str
    severity: Severity
    message: str
    path: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "line": self.line,
        }


@dataclass(frozen=True)
class ReviewReport:
    findings: tuple[ReviewFinding, ...]
    blocking_count: int
    advisory_count: int
    ready_to_commit: bool

    def to_dict(self) -> dict[str, bool | int | list[dict[str, str | int | None]]]:
        return {
            "ready_to_commit": self.ready_to_commit,
            "blocking_count": self.blocking_count,
            "advisory_count": self.advisory_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def run_review(repo_root: Path) -> ReviewReport:
    status_output = _git_status_porcelain(repo_root)
    tracked_files = _git_tracked_files(repo_root)

    findings: list[ReviewFinding] = []
    findings.extend(_find_worktree_dirty_findings(status_output))
    findings.extend(_find_conflict_markers(repo_root, tracked_files))
    findings.extend(_find_todo_markers(repo_root, tracked_files))

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (
                0 if item.severity == "blocking" else 1,
                item.path or "",
                item.line or 0,
                item.check_id,
            ),
        )
    )
    blocking_count = sum(1 for finding in ordered if finding.severity == "blocking")
    advisory_count = len(ordered) - blocking_count
    return ReviewReport(
        findings=ordered,
        blocking_count=blocking_count,
        advisory_count=advisory_count,
        ready_to_commit=blocking_count == 0,
    )


def _git_status_porcelain(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        check=False,
        cwd=repo_root,
        text=True,
    )
    return result.stdout


def _git_tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        check=False,
        cwd=repo_root,
        text=True,
    )
    return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]


def _find_worktree_dirty_findings(status_output: str) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for line in status_output.splitlines():
        if not line.strip():
            continue
        raw_path = line[3:].strip() if len(line) > 3 else ""
        path = raw_path.split(" -> ")[-1] if raw_path else None
        findings.append(
            ReviewFinding(
                check_id="worktree-dirty",
                severity="blocking",
                message="Working tree has uncommitted changes.",
                path=path,
            )
        )
    return findings


def _find_conflict_markers(repo_root: Path, tracked_files: list[Path]) -> list[ReviewFinding]:
    markers = ("<<<<<<<", "=======", ">>>>>>>")
    findings: list[ReviewFinding] = []
    for relative_path in tracked_files:
        target = repo_root / relative_path
        if not _is_scannable_text_file(target):
            continue
        for line_number, line in _read_lines(target):
            if any(marker in line for marker in markers):
                findings.append(
                    ReviewFinding(
                        check_id="merge-conflict-marker",
                        severity="blocking",
                        message="Merge conflict marker detected.",
                        path=relative_path.as_posix(),
                        line=line_number,
                    )
                )
    return findings


def _find_todo_markers(repo_root: Path, tracked_files: list[Path]) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for relative_path in tracked_files:
        target = repo_root / relative_path
        if not _is_scannable_text_file(target):
            continue
        for line_number, line in _read_lines(target):
            if "TODO" not in line and "FIXME" not in line:
                continue
            findings.append(
                ReviewFinding(
                    check_id="todo-marker",
                    severity="advisory",
                    message="TODO/FIXME marker found; confirm it is intentional.",
                    path=relative_path.as_posix(),
                    line=line_number,
                )
            )
    return findings


def _is_scannable_text_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and path.stat().st_size <= 1_000_000
    )


def _read_lines(path: Path) -> list[tuple[int, str]]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return list(enumerate(content.splitlines(), start=1))
