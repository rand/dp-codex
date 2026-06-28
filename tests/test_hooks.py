from __future__ import annotations

import json
import shutil
from pathlib import Path

from dp.cli.main import main

FIXTURES = Path("tests/fixtures/spec81_projects")


def test_hooks_audit_detects_llm_hook(tmp_path: Path, monkeypatch, capsys) -> None:
    shutil.copytree(FIXTURES / "repo_with_conflicting_hooks", tmp_path, dirs_exist_ok=True)
    monkeypatch.chdir(tmp_path)

    assert main(["hooks", "audit", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    codes = {finding["code"] for finding in payload["findings"]}
    assert "hook_calls_llm" in codes


def test_hooks_scaffold_previews_without_writing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["hooks", "scaffold", "--target", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["installed"] is False
    assert not (tmp_path / ".dp/hook-templates/codex/hooks.json").exists()
