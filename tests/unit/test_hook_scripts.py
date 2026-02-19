from __future__ import annotations

import stat
from pathlib import Path


def test_pre_commit_hook_script_targets_pre_commit_enforcement() -> None:
    path = Path("hooks/pre-commit")
    content = path.read_text(encoding="utf-8")

    assert content.startswith("#!/usr/bin/env bash")
    assert "dp enforce pre-commit" in content
    assert path.stat().st_mode & stat.S_IXUSR


def test_pre_push_hook_script_targets_pre_push_enforcement() -> None:
    path = Path("hooks/pre-push")
    content = path.read_text(encoding="utf-8")

    assert content.startswith("#!/usr/bin/env bash")
    assert "dp enforce pre-push" in content
    assert path.stat().st_mode & stat.S_IXUSR
