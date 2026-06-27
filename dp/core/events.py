from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# @trace SPEC-80.02

@dataclass(frozen=True)
class EventAppendResult:
    path: str
    event: dict[str, Any]


def append_jsonl_event(path: Path, event: dict[str, Any]) -> EventAppendResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True))
        stream.write("\n")
    return EventAppendResult(path=path.as_posix(), event=event)


def read_jsonl_events(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()

    events: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Event log {path.as_posix()} contains malformed JSON on line {line_number}."
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(
                f"Event log {path.as_posix()} line {line_number} must be a JSON object."
            )
        events.append(payload)
    return tuple(events)
