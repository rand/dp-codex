from pathlib import Path

from dp.core.trace_parser import parse_trace_markers, parse_trace_references


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_trace_markers_supports_configured_languages_and_stable_order(
    tmp_path: Path,
) -> None:
    python_file = tmp_path / "dp/core/sample.py"
    typescript_file = tmp_path / "tests/sample.ts"
    ignored_file = tmp_path / "notes.txt"

    _write(
        python_file,
        "\n".join(
            (
                "# @trace SPEC-01.01",
                "x = 1  # @trace SPEC-02.02",
            )
        ),
    )
    _write(typescript_file, "// @trace SPEC-01.01")
    _write(ignored_file, "@trace SPEC-99.99")

    parsed = parse_trace_markers([ignored_file, typescript_file, python_file, typescript_file])

    assert [
        (item.spec_id, item.location.path, item.location.line, item.location.column)
        for item in parsed
    ] == [
        ("SPEC-01.01", python_file.as_posix(), 1, 10),
        ("SPEC-02.02", python_file.as_posix(), 2, 17),
        ("SPEC-01.01", typescript_file.as_posix(), 1, 11),
    ]


def test_parse_trace_markers_ignores_invalid_spec_ids(tmp_path: Path) -> None:
    source = tmp_path / "tests/invalid.py"
    _write(
        source,
        "\n".join(
            (
                "# @trace SPEC-1.01",
                "# @trace SPEC-AA.BB",
                "# @trace SPEC-12.34",
            )
        ),
    )

    parsed = parse_trace_markers([source])

    assert [item.spec_id for item in parsed] == ["SPEC-12.34"]


def test_parse_trace_references_reports_malformed_entries(tmp_path: Path) -> None:
    source = tmp_path / "tests/malformed.py"
    _write(
        source,
        "\n".join(
            (
                "# @trace",
                "# @trace SPEC-4.04",
            )
        ),
    )

    parsed, malformed = parse_trace_references([source])

    assert parsed == []
    assert len(malformed) == 2
    assert malformed[0].raw_value is None
    assert "Expected format: SPEC-XX.YY" in malformed[0].message
    assert malformed[1].raw_value == "SPEC-4.04"
    assert "Malformed trace reference" in malformed[1].message


def test_parse_trace_markers_supports_multiple_markers_on_one_line(tmp_path: Path) -> None:
    source = tmp_path / "tests/multi.py"
    _write(source, "# @trace SPEC-11.11 and @trace SPEC-22.22")

    parsed = parse_trace_markers([source])

    assert [(item.spec_id, item.location.line) for item in parsed] == [
        ("SPEC-11.11", 1),
        ("SPEC-22.22", 1),
    ]


def test_parse_trace_markers_ignores_python_string_literals(tmp_path: Path) -> None:
    source = tmp_path / "tests/literals.py"
    _write(
        source,
        "\n".join(
            (
                'example = "# @trace SPEC-01.01"',
                "# @trace SPEC-02.02",
            )
        ),
    )

    parsed = parse_trace_markers([source])

    assert [item.spec_id for item in parsed] == ["SPEC-02.02"]
