from __future__ import annotations

import shutil
from pathlib import Path

from dp.core.adoption import inspect_adoption, plan_adoption

FIXTURES = Path("tests/fixtures/spec81_projects")


def test_adopt_inspect_classifies_fixture_projects() -> None:
    not_adopted = inspect_adoption(FIXTURES / "not_adopted_project")
    legacy = inspect_adoption(FIXTURES / "old_dp_project_minimal")
    current = inspect_adoption(FIXTURES / "spec80_project_current")

    assert not_adopted.payload["classification"] == "not_adopted"
    assert legacy.payload["classification"] == "legacy_dp"
    assert current.payload["classification"] == "current_spec80"


def test_adopt_plan_write_creates_reviewable_artifacts(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES / "old_dp_project_with_agents_md", tmp_path, dirs_exist_ok=True)

    result = plan_adoption(tmp_path, write=True)

    assert result.exit_code == 0
    artifacts = result.payload["artifacts"]
    assert len(artifacts) == 2
    assert (tmp_path / artifacts[0]["path"]).exists()
    assert result.payload["plan"]["rules"]["overwrite_agents_md"] is False
    assert (
        (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        == "# Agent Instructions\n\nExisting project law.\n"
    )
