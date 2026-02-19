from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_trace_coverage_command_outputs_json_report(tmp_path: Path, capsys, monkeypatch) -> None:
    _write(
        tmp_path / "docs/specs/spec.md",
        "\n".join(
            (
                "[SPEC-01.01]",
                "[SPEC-02.02]",
            )
        ),
    )
    _write(tmp_path / "dp/core/example.py", "# @trace SPEC-01.01")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "trace",
            "coverage",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "dp/**/*.py",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["total_specs"] == 2
    assert output["covered_count"] == 1
    assert output["uncovered_specs"] == ["SPEC-02.02"]


def test_trace_coverage_command_outputs_text_report(tmp_path: Path, capsys, monkeypatch) -> None:
    _write(
        tmp_path / "docs/specs/spec.md",
        "\n".join(
            (
                "[SPEC-10.10]",
                "[SPEC-20.20]",
            )
        ),
    )
    _write(tmp_path / "tests/sample.py", "# @trace SPEC-10.10")

    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "trace",
            "coverage",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "tests/**/*.py",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out.splitlines()
    assert "total_specs: 2" in output
    assert "covered_count: 1" in output
    assert "uncovered_specs:" in output
    assert "- SPEC-20.20" in output


def test_trace_validate_command_returns_non_zero_with_actionable_diagnostics(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _write(tmp_path / "docs/specs/spec.md", "[SPEC-01.01]")
    _write(
        tmp_path / "tests/sample.py",
        "\n".join(
            (
                "# @trace SPEC-02.02",
                "# @trace SPEC-2.02",
            )
        ),
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "trace",
            "validate",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "tests/**/*.py",
        ]
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "trace validation failed" in output
    assert "[unresolved]" in output
    assert "[malformed]" in output


def test_trace_validate_command_outputs_json(tmp_path: Path, capsys, monkeypatch) -> None:
    _write(tmp_path / "docs/specs/spec.md", "[SPEC-77.77]")
    _write(tmp_path / "tests/sample.py", "# @trace SPEC-77.77")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "trace",
            "validate",
            "--json",
            "--spec-glob",
            "docs/specs/**/*.md",
            "--trace-glob",
            "tests/**/*.py",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert output["error_count"] == 0
