from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# @trace SPEC-80.17
DEFAULT_EVIDENCE_RUN_DIR = Path("docs/evidence-runs")


def default_evidence_run_path(goal_id: str | None) -> Path:
    slug = _path_slug(goal_id or "goal")
    return DEFAULT_EVIDENCE_RUN_DIR / f"RUN-{slug}.json"


def evidence_artifact_commands(
    *,
    goal_path: Path,
    goal_id: str | None,
    evidence_plan: str | None,
) -> dict[str, str]:
    goal_text = goal_path.as_posix()
    run_path = default_evidence_run_path(goal_id).as_posix()
    plan_text = evidence_plan or "<evidence.json>"
    return {
        "evidence_run": f"dp evidence run {plan_text} --output {run_path} --force --json",
        "complete": f"dp goal complete {goal_text} --evidence {run_path} --json",
        "verify": f"dp verify --goal {goal_text} --evidence {run_path} --json",
        "verify_fresh": (
            f"dp verify --goal {goal_text} --evidence-output {run_path} --force --json"
        ),
    }


def artifact_ref(path: Path, *, written: bool) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "written": written,
    }


def validate_evidence_output_path(path: Path) -> dict[str, str] | None:
    text = path.as_posix()
    if not text.strip():
        return _error("invalid_output_path", "$.output", "Output path must be non-empty.")
    if path.is_absolute() or text.startswith(("~", "-")):
        return _error(
            "invalid_output_path",
            "$.output",
            "Output path must be a sane relative path.",
        )
    if ".." in path.parts:
        return _error(
            "invalid_output_path",
            "$.output",
            "Output path must not contain '..' path parts.",
        )
    if path.suffix != ".json":
        return _error("invalid_output_path", "$.output", "Output path must end in .json.")
    return None


def _path_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    slug = slug.strip(".-")
    return slug or "goal"


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "path": path,
        "message": message,
    }
