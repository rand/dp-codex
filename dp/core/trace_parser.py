from __future__ import annotations

import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .spec_parser import SourceLocation

TRACE_TOKEN_PATTERN = re.compile(r"@trace(?:\s+([^\s]+))?")
SPEC_ID_PATTERN = re.compile(r"SPEC-\d{2}\.\d{2}")

SUPPORTED_TRACE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".md",
    ".py",
    ".pyi",
    ".rs",
    ".sh",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class TraceMarker:
    spec_id: str
    location: SourceLocation


@dataclass(frozen=True)
class MalformedTraceMarker:
    location: SourceLocation
    raw_value: str | None
    message: str


def parse_trace_markers(paths: Iterable[str | Path]) -> list[TraceMarker]:
    markers, _ = parse_trace_references(paths)
    return markers


def parse_trace_references(
    paths: Iterable[str | Path],
) -> tuple[list[TraceMarker], list[MalformedTraceMarker]]:
    normalized_paths = sorted({Path(path) for path in paths}, key=lambda path: path.as_posix())
    markers: list[TraceMarker] = []
    malformed: list[MalformedTraceMarker] = []

    for path in normalized_paths:
        if not _is_supported_trace_path(path):
            continue
        parsed_markers, malformed_markers = _scan_file(path)
        markers.extend(parsed_markers)
        malformed.extend(malformed_markers)

    return (
        sorted(
            markers,
            key=lambda marker: (
                marker.location.path,
                marker.location.line,
                marker.location.column,
                marker.spec_id,
            ),
        ),
        sorted(
            malformed,
            key=lambda issue: (
                issue.location.path,
                issue.location.line,
                issue.location.column,
            ),
        ),
    )


def _is_supported_trace_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_TRACE_SUFFIXES


def _scan_file(path: Path) -> tuple[list[TraceMarker], list[MalformedTraceMarker]]:
    content = path.read_text(encoding="utf-8")

    if path.suffix.lower() in {".py", ".pyi"}:
        return _scan_python_comments(path, content)
    return _scan_text_content(path, content)


def _scan_text_content(
    path: Path,
    content: str,
) -> tuple[list[TraceMarker], list[MalformedTraceMarker]]:
    markers: list[TraceMarker] = []
    malformed: list[MalformedTraceMarker] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        _scan_trace_tokens(
            path=path,
            line_number=line_number,
            snippet=line,
            column_offset=0,
            markers=markers,
            malformed=malformed,
        )
    return markers, malformed


def _scan_python_comments(
    path: Path,
    content: str,
) -> tuple[list[TraceMarker], list[MalformedTraceMarker]]:
    markers: list[TraceMarker] = []
    malformed: list[MalformedTraceMarker] = []
    reader = io.StringIO(content).readline

    try:
        tokens = tokenize.generate_tokens(reader)
    except tokenize.TokenError:
        return _scan_text_content(path, content)

    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue

        line_number, start_column = token.start
        _scan_trace_tokens(
            path=path,
            line_number=line_number,
            snippet=token.string,
            column_offset=start_column,
            markers=markers,
            malformed=malformed,
        )

    return markers, malformed


def _normalize_trace_token(value: str) -> str:
    return value.rstrip(".,;:)]}")


def _scan_trace_tokens(
    *,
    path: Path,
    line_number: int,
    snippet: str,
    column_offset: int,
    markers: list[TraceMarker],
    malformed: list[MalformedTraceMarker],
) -> None:
    for match in TRACE_TOKEN_PATTERN.finditer(snippet):
        raw_value = match.group(1)
        raw_column = match.start(1) if raw_value is not None else match.start()
        location = SourceLocation(
            path=path.as_posix(),
            line=line_number,
            column=column_offset + raw_column + 1,
        )

        if raw_value is None:
            malformed.append(
                MalformedTraceMarker(
                    location=location,
                    raw_value=None,
                    message="Missing spec ID after @trace. Expected format: SPEC-XX.YY.",
                )
            )
            continue

        normalized = _normalize_trace_token(raw_value)
        if SPEC_ID_PATTERN.fullmatch(normalized):
            markers.append(
                TraceMarker(
                    spec_id=normalized,
                    location=location,
                )
            )
            continue

        malformed.append(
            MalformedTraceMarker(
                location=location,
                raw_value=raw_value,
                message=(
                    f"Malformed trace reference '{raw_value}'. "
                    "Expected format: SPEC-XX.YY."
                ),
            )
        )
