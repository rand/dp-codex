from __future__ import annotations

import json
from pathlib import Path

from dp.core.adoption import apply_adoption


def test_adopt_apply_is_dry_run_by_default(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path, conflicts=[])

    result = apply_adoption(plan_path, repo_root=tmp_path)

    assert result.exit_code == 0
    assert result.payload["dry_run"] is True
    assert not (tmp_path / ".dp/goals").exists()


def test_adopt_apply_explicit_apply_creates_apply_mode_dirs(tmp_path: Path) -> None:
    plan_path = _write_plan(tmp_path, conflicts=[])

    result = apply_adoption(plan_path, apply=True, repo_root=tmp_path)

    assert result.exit_code == 0
    assert (tmp_path / ".dp/goals").exists()


def test_adopt_apply_stops_on_conflicts(tmp_path: Path) -> None:
    plan_path = _write_plan(
        tmp_path,
        conflicts=[{"code": "conflict", "path": "AGENTS.md", "summary": "conflict"}],
    )

    result = apply_adoption(plan_path, apply=True, repo_root=tmp_path)

    assert result.exit_code == 1
    assert result.payload["status"] == "blocked"


def _write_plan(tmp_path: Path, *, conflicts: list[dict[str, str]]) -> Path:
    payload = {
        "schema_version": "dp.adoption_plan.v1",
        "id": "MIGRATION-test",
        "status": "planned",
        "source_state": {"classification": "legacy_dp"},
        "changes": [
            {
                "id": "create-goal-event-dir",
                "kind": "mkdir",
                "path": ".dp/goals",
                "mode": "apply",
                "reason": "test",
            }
        ],
        "conflicts": conflicts,
        "verification": [],
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
