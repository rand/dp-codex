from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ADR_ID_PATTERN = re.compile(r"ADR-(\d{4})")
ADR_FILE_PATTERN = re.compile(r"^(ADR-\d{4})-(.+)\.md$")
ADR_STATUSES = ("proposal", "accepted", "superseded", "deprecated")
ADR_TRANSITIONS = {
    "proposal": {"proposal", "accepted", "deprecated"},
    "accepted": {"accepted", "superseded", "deprecated"},
    "superseded": {"superseded"},
    "deprecated": {"deprecated"},
}


@dataclass(frozen=True)
class AdrRecord:
    adr_id: str
    title: str
    status: str
    created: str
    updated: str
    superseded_by: str | None
    path: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "id": self.adr_id,
            "title": self.title,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "superseded_by": self.superseded_by,
            "path": self.path,
        }


def create_adr(title: str, directory: Path, status: str = "proposal") -> AdrRecord:
    normalized_status = _normalize_status(status)
    directory.mkdir(parents=True, exist_ok=True)
    adr_id = _next_adr_id(directory)
    slug = _slugify(title)
    target = directory / f"{adr_id}-{slug}.md"
    today = date.today().isoformat()

    record = AdrRecord(
        adr_id=adr_id,
        title=title,
        status=normalized_status,
        created=today,
        updated=today,
        superseded_by=None,
        path=target.as_posix(),
    )
    target.write_text(_render(record, _default_body()), encoding="utf-8")
    return record


def list_adrs(directory: Path) -> list[AdrRecord]:
    if not directory.exists():
        return []

    records = [_read_adr(path)[0] for path in sorted(directory.glob("ADR-*.md")) if path.is_file()]
    return sorted(records, key=lambda record: record.adr_id)


def show_adr(identifier: str, directory: Path) -> tuple[AdrRecord, str]:
    path = _resolve_adr_path(identifier, directory)
    record, body = _read_adr(path)
    return record, _render(record, body)


def update_adr_status(
    identifier: str,
    status: str,
    directory: Path,
    superseded_by: str | None = None,
) -> AdrRecord:
    target_status = _normalize_status(status)
    path = _resolve_adr_path(identifier, directory)
    record, body = _read_adr(path)

    if target_status not in ADR_TRANSITIONS[record.status]:
        raise ValueError(
            f"Invalid transition {record.status} -> {target_status}. "
            f"Allowed: {', '.join(sorted(ADR_TRANSITIONS[record.status]))}."
        )

    normalized_superseded_by: str | None = None
    if target_status == "superseded":
        if superseded_by is None:
            raise ValueError("Superseding an ADR requires --superseded-by ADR-XXXX.")
        normalized_superseded_by = _normalize_adr_id(superseded_by)
    elif superseded_by is not None:
        raise ValueError("--superseded-by can only be used when status is superseded.")

    updated = AdrRecord(
        adr_id=record.adr_id,
        title=record.title,
        status=target_status,
        created=record.created,
        updated=date.today().isoformat(),
        superseded_by=normalized_superseded_by,
        path=record.path,
    )

    path.write_text(_render(updated, body), encoding="utf-8")
    return updated


def _resolve_adr_path(identifier: str, directory: Path) -> Path:
    candidate = Path(identifier)
    if candidate.exists():
        return candidate

    normalized_id = _normalize_adr_id(identifier)
    matches = sorted(directory.glob(f"{normalized_id}-*.md"))
    if not matches:
        raise ValueError(f"ADR '{identifier}' was not found in {directory.as_posix()}.")
    if len(matches) > 1:
        raise ValueError(f"ADR '{identifier}' matched multiple files; resolve manually.")
    return matches[0]


def _next_adr_id(directory: Path) -> str:
    max_index = 0
    for path in directory.glob("ADR-*.md"):
        match = ADR_FILE_PATTERN.match(path.name)
        if not match:
            continue
        max_index = max(max_index, int(match.group(1).split("-")[1]))
    return f"ADR-{max_index + 1:04d}"


def _read_adr(path: Path) -> tuple[AdrRecord, str]:
    content = path.read_text(encoding="utf-8")
    metadata, body = _parse_front_matter(content)

    adr_id = _normalize_adr_id(metadata["id"])
    status = _normalize_status(metadata["status"])
    title = metadata["title"]
    created = metadata["created"]
    updated = metadata["updated"]
    superseded_by = metadata.get("superseded_by") or None
    if superseded_by is not None:
        superseded_by = _normalize_adr_id(superseded_by)

    record = AdrRecord(
        adr_id=adr_id,
        title=title,
        status=status,
        created=created,
        updated=updated,
        superseded_by=superseded_by,
        path=path.as_posix(),
    )
    return record, body


def _parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        raise ValueError("ADR file missing front matter block.")

    _, _, rest = content.partition("---\n")
    metadata_block, separator, body = rest.partition("---\n")
    if not separator:
        raise ValueError("ADR file missing front matter closing delimiter.")

    metadata: dict[str, str] = {}
    for raw_line in metadata_block.strip().splitlines():
        if not raw_line.strip():
            continue
        key, sep, value = raw_line.partition(":")
        if not sep:
            raise ValueError(f"Invalid metadata line '{raw_line}' in ADR front matter.")
        metadata[key.strip()] = value.strip()

    required = {"id", "title", "status", "created", "updated", "superseded_by"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise ValueError(f"ADR front matter missing keys: {', '.join(missing)}.")

    cleaned_body = body.lstrip("\n")
    return metadata, cleaned_body


def _render(record: AdrRecord, body: str) -> str:
    superseded_by = record.superseded_by or ""
    return (
        "---\n"
        f"id: {record.adr_id}\n"
        f"title: {record.title}\n"
        f"status: {record.status}\n"
        f"created: {record.created}\n"
        f"updated: {record.updated}\n"
        f"superseded_by: {superseded_by}\n"
        "---\n\n"
        f"{body.rstrip()}\n"
    )


def _default_body() -> str:
    return (
        "## Context\n\n"
        "TBD\n\n"
        "## Decision\n\n"
        "TBD\n\n"
        "## Consequences\n\n"
        "TBD\n"
    )


def _normalize_adr_id(value: str) -> str:
    candidate = value.strip().upper()
    match = ADR_ID_PATTERN.fullmatch(candidate)
    if not match:
        raise ValueError(f"Invalid ADR ID '{value}'. Expected format ADR-XXXX.")
    return f"ADR-{int(match.group(1)):04d}"


def _normalize_status(value: str) -> str:
    candidate = value.strip().lower()
    if candidate not in ADR_STATUSES:
        raise ValueError(
            f"Invalid ADR status '{value}'. Use one of: {', '.join(ADR_STATUSES)}."
        )
    return candidate


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return slug or "untitled"
