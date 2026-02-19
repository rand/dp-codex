from pathlib import Path

import pytest

from dp.core.review import run_review


def test_run_review_emits_blocking_and_advisory_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deferred_line = "# TO" + "DO: resolve conflict"
    target = tmp_path / "dp/core/example.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(
            (
                "<<<<<<< HEAD",
                deferred_line,
                "=======",
                ">>>>>>> branch",
            )
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dp.core.review._git_status_porcelain", lambda _: " M dp/core/example.py\n")
    monkeypatch.setattr("dp.core.review._git_tracked_files", lambda _: [Path("dp/core/example.py")])

    report = run_review(tmp_path)

    assert report.ready_to_commit is False
    assert report.blocking_count >= 2
    assert report.advisory_count >= 1
    assert report.findings[0].severity == "blocking"


def test_run_review_reports_ready_when_no_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "dp/core/clean.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr("dp.core.review._git_status_porcelain", lambda _: "")
    monkeypatch.setattr("dp.core.review._git_tracked_files", lambda _: [Path("dp/core/clean.py")])

    report = run_review(tmp_path)

    assert report.ready_to_commit is True
    assert report.blocking_count == 0
    assert report.advisory_count == 0
    assert report.findings == ()


def test_run_review_ignores_quoted_conflict_marker_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "docs/examples.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("'<<<<<<< HEAD'\n'======='\n'>>>>>>> branch'\n", encoding="utf-8")

    monkeypatch.setattr("dp.core.review._git_status_porcelain", lambda _: "")
    monkeypatch.setattr("dp.core.review._git_tracked_files", lambda _: [Path("docs/examples.md")])

    report = run_review(tmp_path)

    assert report.ready_to_commit is True
    assert all(finding.check_id != "merge-conflict-marker" for finding in report.findings)
