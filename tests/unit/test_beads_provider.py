from __future__ import annotations

import subprocess
from typing import Any

import pytest

from dp.providers.beads import BeadsNotInitializedError, run_bd


def test_run_bd_requires_beads_context(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(BeadsNotInitializedError):
        run_bd(["ready"])


def test_run_bd_works_from_nested_path_with_repo_beads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".beads").mkdir(parents=True)
    nested_workdir = repo_root / "nested" / "path"
    nested_workdir.mkdir(parents=True)
    monkeypatch.chdir(nested_workdir)

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr("dp.providers.beads.subprocess.run", fake_run)

    result = run_bd(["ready"])

    assert calls == [["bd", "ready"]]
    assert result.returncode == 0
    assert result.stdout == "ok\n"
