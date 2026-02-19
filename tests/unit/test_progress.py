from __future__ import annotations

from pathlib import Path

from dp.core.progress import (
    ProgressReport,
    ProgressSnapshot,
    WatchTrigger,
    evaluate_watch_triggers,
    load_snapshot,
    write_progress_report,
)


def test_evaluate_watch_triggers_with_previous_snapshot() -> None:
    previous = ProgressSnapshot(
        timestamp_utc="2026-02-19T10:00:00+00:00",
        dirty_files=0,
        spec_count=1,
        adr_count=1,
        ready_issue_count=2,
    )
    current = ProgressSnapshot(
        timestamp_utc="2026-02-19T10:05:00+00:00",
        dirty_files=3,
        spec_count=2,
        adr_count=1,
        ready_issue_count=4,
    )

    triggers = evaluate_watch_triggers(current, previous)

    assert [trigger.name for trigger in triggers] == [
        "working-tree-dirty",
        "ready-issue-growth",
        "spec-count-change",
    ]
    assert [trigger.triggered for trigger in triggers] == [True, True, True]


def test_write_progress_report_and_load_snapshot_round_trip(tmp_path: Path) -> None:
    report = ProgressReport(
        snapshot=ProgressSnapshot(
            timestamp_utc="2026-02-19T10:00:00+00:00",
            dirty_files=1,
            spec_count=2,
            adr_count=3,
            ready_issue_count=4,
        ),
        triggers=(
            WatchTrigger(
                name="working-tree-dirty",
                triggered=True,
                reason="dirty_files=1",
            ),
        ),
    )

    json_path, markdown_path = write_progress_report(report, tmp_path)
    loaded = load_snapshot(json_path)

    assert json_path.exists()
    assert markdown_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "## Agent Bootstrap" in markdown
    assert loaded.dirty_files == 1
    assert loaded.spec_count == 2
