from dp.core.spec_parser import ParsedSpec, SourceLocation
from dp.core.trace_parser import MalformedTraceMarker, TraceMarker
from dp.core.validation import validate_trace_references


def test_validate_trace_references_flags_unresolved_and_malformed_markers() -> None:
    parsed_specs = (
        ParsedSpec(
            spec_id="SPEC-01.01",
            locations=(SourceLocation(path="docs/specs/spec.md", line=1, column=2),),
        ),
    )
    parsed_markers = (
        TraceMarker(
            spec_id="SPEC-99.99",
            location=SourceLocation(path="dp/core/example.py", line=3, column=10),
        ),
    )
    malformed_markers = (
        MalformedTraceMarker(
            location=SourceLocation(path="dp/core/example.py", line=4, column=10),
            raw_value="SPEC-1.01",
            message="Malformed trace reference 'SPEC-1.01'. Expected format: SPEC-XX.YY.",
        ),
    )

    report = validate_trace_references(parsed_specs, parsed_markers, malformed_markers)

    assert report.is_valid is False
    assert len(report.issues) == 2
    assert [issue.kind for issue in report.issues] == ["unresolved", "malformed"]


def test_validate_trace_references_passes_when_all_markers_resolve() -> None:
    parsed_specs = (
        ParsedSpec(
            spec_id="SPEC-01.01",
            locations=(SourceLocation(path="docs/specs/spec.md", line=1, column=2),),
        ),
    )
    parsed_markers = (
        TraceMarker(
            spec_id="SPEC-01.01",
            location=SourceLocation(path="dp/core/example.py", line=3, column=10),
        ),
    )

    report = validate_trace_references(parsed_specs, parsed_markers, malformed_markers=())

    assert report.is_valid is True
    assert report.issues == ()
