from pathlib import Path

from dp.core.coverage import compute_trace_coverage
from dp.core.spec_parser import parse_spec_ids
from dp.core.trace_parser import parse_trace_markers, parse_trace_references
from dp.core.validation import validate_trace_references


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_malformed_ids_are_reported_by_trace_validation(tmp_path: Path) -> None:
    spec_file = tmp_path / "docs/specs/spec.md"
    trace_file = tmp_path / "tests/sample.py"

    _write(spec_file, "[SPEC-01.01]\n[SPEC-1.01]\n")
    _write(trace_file, "# @trace SPEC-01.01\n# @trace SPEC-1.01\n")

    parsed_specs = parse_spec_ids([spec_file])
    parsed_markers, malformed_markers = parse_trace_references([trace_file])
    report = validate_trace_references(parsed_specs, parsed_markers, malformed_markers)

    assert [entry.spec_id for entry in parsed_specs] == ["SPEC-01.01"]
    assert report.is_valid is False
    assert any(issue.kind == "malformed" for issue in report.issues)


def test_duplicate_spec_ids_are_deduped_for_coverage(tmp_path: Path) -> None:
    first = tmp_path / "docs/specs/first.md"
    second = tmp_path / "docs/specs/second.md"
    trace_file = tmp_path / "dp/core/sample.py"

    _write(first, "[SPEC-02.02]\n")
    _write(second, "[SPEC-02.02]\n[SPEC-03.03]\n")
    _write(trace_file, "# @trace SPEC-02.02")

    report = compute_trace_coverage(
        parsed_specs=parse_spec_ids([first, second]),
        parsed_markers=parse_trace_markers([trace_file]),
    )

    assert report.total_specs == 2
    assert report.covered_count == 1
    assert report.uncovered_specs == ("SPEC-03.03",)


def test_mixed_language_trace_files_are_supported(tmp_path: Path) -> None:
    python_file = tmp_path / "dp/core/sample.py"
    typescript_file = tmp_path / "dp/cli/sample.ts"
    rust_file = tmp_path / "dp/core/sample.rs"
    unsupported_file = tmp_path / "notes.txt"

    _write(python_file, "# @trace SPEC-10.10")
    _write(typescript_file, "// @trace SPEC-20.20")
    _write(rust_file, "// @trace SPEC-30.30")
    _write(unsupported_file, "@trace SPEC-99.99")

    parsed = parse_trace_markers([python_file, typescript_file, rust_file, unsupported_file])

    assert sorted(entry.spec_id for entry in parsed) == ["SPEC-10.10", "SPEC-20.20", "SPEC-30.30"]


def test_large_file_trace_scan_keeps_boundary_line_numbers(tmp_path: Path) -> None:
    large_file = tmp_path / "tests/large.py"
    line_count = 2048
    lines = ["# filler"] * line_count
    lines[0] = "# @trace SPEC-10.10"
    lines[-1] = "# @trace SPEC-20.20"
    _write(large_file, "\n".join(lines))

    parsed = parse_trace_markers([large_file])

    assert [(entry.spec_id, entry.location.line) for entry in parsed] == [
        ("SPEC-10.10", 1),
        ("SPEC-20.20", line_count),
    ]
