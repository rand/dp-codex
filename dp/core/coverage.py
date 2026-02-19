from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .spec_parser import ParsedSpec
from .trace_parser import TraceMarker


@dataclass(frozen=True)
class TraceCoverageReport:
    total_specs: int
    covered_count: int
    covered_specs: tuple[str, ...]
    uncovered_specs: tuple[str, ...]

    def to_dict(self) -> dict[str, int | list[str]]:
        return {
            "total_specs": self.total_specs,
            "covered_count": self.covered_count,
            "covered_specs": list(self.covered_specs),
            "uncovered_specs": list(self.uncovered_specs),
        }


def compute_trace_coverage(
    parsed_specs: Iterable[ParsedSpec], parsed_markers: Iterable[TraceMarker]
) -> TraceCoverageReport:
    spec_ids = {entry.spec_id for entry in parsed_specs}
    traced_spec_ids = {entry.spec_id for entry in parsed_markers}

    covered = tuple(sorted(spec_ids & traced_spec_ids))
    uncovered = tuple(sorted(spec_ids - traced_spec_ids))

    return TraceCoverageReport(
        total_specs=len(spec_ids),
        covered_count=len(covered),
        covered_specs=covered,
        uncovered_specs=uncovered,
    )
