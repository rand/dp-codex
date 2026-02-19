from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SPEC_ID_PATTERN = re.compile(r"\[(SPEC-\d{2}\.\d{2})\]")


@dataclass(frozen=True, order=True)
class SourceLocation:
    path: str
    line: int
    column: int


@dataclass(frozen=True)
class ParsedSpec:
    spec_id: str
    locations: tuple[SourceLocation, ...]


def parse_spec_ids(paths: Iterable[str | Path]) -> list[ParsedSpec]:
    normalized_paths = sorted({Path(path) for path in paths}, key=lambda path: path.as_posix())
    locations_by_spec: dict[str, set[SourceLocation]] = {}

    for path in normalized_paths:
        for location, spec_id in _scan_file(path):
            locations_by_spec.setdefault(spec_id, set()).add(location)

    parsed_specs: list[ParsedSpec] = []
    for spec_id in sorted(locations_by_spec):
        parsed_specs.append(
            ParsedSpec(
                spec_id=spec_id,
                locations=tuple(sorted(locations_by_spec[spec_id])),
            )
        )

    return parsed_specs


def _scan_file(path: Path) -> list[tuple[SourceLocation, str]]:
    matches: list[tuple[SourceLocation, str]] = []
    content = path.read_text(encoding="utf-8")

    for line_number, line in enumerate(content.splitlines(), start=1):
        for match in SPEC_ID_PATTERN.finditer(line):
            matches.append(
                (
                    SourceLocation(
                        path=path.as_posix(),
                        line=line_number,
                        column=match.start(1) + 1,
                    ),
                    match.group(1),
                )
            )

    return matches
