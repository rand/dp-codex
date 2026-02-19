from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .spec_parser import ParsedSpec, SourceLocation
from .trace_parser import MalformedTraceMarker, TraceMarker

IssueKind = Literal["malformed", "unresolved"]


@dataclass(frozen=True)
class TraceValidationIssue:
    kind: IssueKind
    location: SourceLocation
    message: str
    spec_id: str | None = None
    raw_value: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "kind": self.kind,
            "path": self.location.path,
            "line": self.location.line,
            "column": self.location.column,
            "spec_id": self.spec_id,
            "raw_value": self.raw_value,
            "message": self.message,
        }


@dataclass(frozen=True)
class TraceValidationReport:
    is_valid: bool
    issues: tuple[TraceValidationIssue, ...]

    def to_dict(self) -> dict[str, bool | int | list[dict[str, str | int | None]]]:
        return {
            "valid": self.is_valid,
            "error_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_trace_references(
    parsed_specs: Iterable[ParsedSpec],
    parsed_markers: Iterable[TraceMarker],
    malformed_markers: Iterable[MalformedTraceMarker],
) -> TraceValidationReport:
    spec_ids = {entry.spec_id for entry in parsed_specs}
    issues: list[TraceValidationIssue] = []

    for malformed in malformed_markers:
        issues.append(
            TraceValidationIssue(
                kind="malformed",
                location=malformed.location,
                raw_value=malformed.raw_value,
                message=malformed.message,
            )
        )

    for marker in parsed_markers:
        if marker.spec_id in spec_ids:
            continue
        issues.append(
            TraceValidationIssue(
                kind="unresolved",
                location=marker.location,
                spec_id=marker.spec_id,
                message=(
                    f"Trace reference '{marker.spec_id}' has no matching "
                    "[SPEC-XX.YY] definition in spec documents."
                ),
            )
        )

    issues.sort(
        key=lambda issue: (
            issue.location.path,
            issue.location.line,
            issue.location.column,
            issue.kind,
        )
    )

    return TraceValidationReport(
        is_valid=not issues,
        issues=tuple(issues),
    )
