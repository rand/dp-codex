from dp.core.coverage import compute_trace_coverage
from dp.core.spec_parser import ParsedSpec, SourceLocation
from dp.core.trace_parser import TraceMarker


def test_compute_trace_coverage_returns_expected_totals_and_uncovered_list() -> None:
    parsed_specs = (
        ParsedSpec(
            spec_id="SPEC-01.01",
            locations=(SourceLocation(path="docs/specs/spec.md", line=1, column=2),),
        ),
        ParsedSpec(
            spec_id="SPEC-02.02",
            locations=(SourceLocation(path="docs/specs/spec.md", line=2, column=2),),
        ),
        ParsedSpec(
            spec_id="SPEC-03.03",
            locations=(SourceLocation(path="docs/specs/spec.md", line=3, column=2),),
        ),
    )
    parsed_markers = (
        TraceMarker(
            spec_id="SPEC-01.01",
            location=SourceLocation(path="dp/core/example.py", line=10, column=10),
        ),
        TraceMarker(
            spec_id="SPEC-02.02",
            location=SourceLocation(path="dp/core/example.py", line=20, column=10),
        ),
        TraceMarker(
            spec_id="SPEC-99.99",
            location=SourceLocation(path="dp/core/example.py", line=30, column=10),
        ),
    )

    report = compute_trace_coverage(parsed_specs=parsed_specs, parsed_markers=parsed_markers)

    assert report.total_specs == 3
    assert report.covered_count == 2
    assert report.covered_specs == ("SPEC-01.01", "SPEC-02.02")
    assert report.uncovered_specs == ("SPEC-03.03",)


def test_trace_coverage_report_to_dict_is_json_friendly() -> None:
    report = compute_trace_coverage(parsed_specs=(), parsed_markers=())

    assert report.to_dict() == {
        "covered_count": 0,
        "covered_specs": [],
        "total_specs": 0,
        "uncovered_specs": [],
    }
