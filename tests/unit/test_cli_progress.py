from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from dp.core.progress import ProgressSnapshot, WatchTrigger

cli_main = importlib.import_module("dp.cli.main")


def test_progress_cli_one_shot_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    snapshot = ProgressSnapshot(
        timestamp_utc="2026-02-19T10:00:00+00:00",
        dirty_files=0,
        spec_count=2,
        adr_count=1,
        ready_issue_count=3,
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "progress-snapshot.json"
    markdown_path = output_dir / "progress-snapshot.md"
    json_path.write_text("{}", encoding="utf-8")
    markdown_path.write_text("# Progress Snapshot\n", encoding="utf-8")

    monkeypatch.setattr(cli_main, "collect_progress_snapshot", lambda _: snapshot)
    monkeypatch.setattr(
        cli_main,
        "write_progress_report",
        lambda _report, _dir: (json_path, markdown_path),
    )

    exit_code = cli_main.main(["progress", "--output-dir", output_dir.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["snapshot"]["spec_count"] == 2
    assert "agent_bootstrap" in payload
    assert payload["json_path"] == json_path.as_posix()


def test_progress_cli_watch_mode_returns_non_zero_on_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    snapshot = ProgressSnapshot(
        timestamp_utc="2026-02-19T10:00:00+00:00",
        dirty_files=2,
        spec_count=1,
        adr_count=1,
        ready_issue_count=5,
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "progress-snapshot.json"
    markdown_path = output_dir / "progress-snapshot.md"
    json_path.write_text("{}", encoding="utf-8")
    markdown_path.write_text("# Progress Snapshot\n", encoding="utf-8")

    monkeypatch.setattr(cli_main, "collect_progress_snapshot", lambda _: snapshot)
    monkeypatch.setattr(
        cli_main,
        "evaluate_watch_triggers",
        lambda _current, _previous: (
            WatchTrigger(
                name="working-tree-dirty",
                triggered=True,
                reason="dirty_files=2",
            ),
        ),
    )
    monkeypatch.setattr(
        cli_main,
        "write_progress_report",
        lambda _report, _dir: (json_path, markdown_path),
    )

    exit_code = cli_main.main(
        ["progress", "--output-dir", output_dir.as_posix(), "--watch", "--json"]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["agent_bootstrap"]["triggered_checks"] == ["working-tree-dirty"]
    assert payload["triggers"][0]["triggered"] is True
