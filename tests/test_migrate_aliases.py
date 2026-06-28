from __future__ import annotations

import json
import shutil
from pathlib import Path

from dp.cli.main import main

FIXTURES = Path("tests/fixtures/spec81_projects")


def test_migrate_inspect_alias_matches_adopt_flow(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    shutil.copytree(FIXTURES / "old_dp_project_minimal", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["migrate", "inspect", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "legacy_dp"


def test_migrate_plan_alias_writes_plan(tmp_path: Path, monkeypatch, capsys) -> None:
    shutil.copytree(FIXTURES / "old_dp_project_minimal", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["migrate", "plan", "--write", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["write"] is True
    assert Path(payload["artifacts"][0]["path"]).exists()
