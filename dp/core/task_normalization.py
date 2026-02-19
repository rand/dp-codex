from __future__ import annotations

STATUS_ALIASES = {
    "blocked": "blocked",
    "closed": "closed",
    "deferred": "deferred",
    "done": "closed",
    "in_progress": "in_progress",
    "inprogress": "in_progress",
    "in-progress": "in_progress",
    "open": "open",
    "snoozed": "deferred",
    "todo": "open",
    "to-do": "open",
}

PRIORITY_ALIASES = {
    "0": "P0",
    "1": "P1",
    "2": "P2",
    "3": "P3",
    "4": "P4",
    "p0": "P0",
    "p1": "P1",
    "p2": "P2",
    "p3": "P3",
    "p4": "P4",
}

CANONICAL_STATUSES = ("open", "in_progress", "blocked", "closed", "deferred")
CANONICAL_PRIORITIES = ("P0", "P1", "P2", "P3", "P4")


def normalize_status(value: str) -> str:
    key = value.strip().lower()
    if key in STATUS_ALIASES:
        return STATUS_ALIASES[key]

    underscored = key.replace(" ", "_")
    if underscored in STATUS_ALIASES:
        return STATUS_ALIASES[underscored]

    raise ValueError(
        "Invalid status value "
        f"'{value}'. Use one of {', '.join(CANONICAL_STATUSES)} "
        "(aliases: todo, in-progress, inprogress, done, to-do, snoozed)."
    )


def normalize_priority(value: str) -> str:
    key = value.strip().lower()
    if key in PRIORITY_ALIASES:
        return PRIORITY_ALIASES[key]

    raise ValueError(
        f"Invalid priority value '{value}'. Use one of: {', '.join(CANONICAL_PRIORITIES)} or 0-4."
    )
