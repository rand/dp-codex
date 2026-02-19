from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class BdUnavailableError(RuntimeError):
    pass


class BeadsNotInitializedError(RuntimeError):
    pass


def run_bd(args: Sequence[str]) -> CommandResult:
    _require_beads_context()

    try:
        completed = subprocess.run(
            ["bd", *args],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError as exc:
        raise BdUnavailableError(
            "bd command not found. Install Beads CLI and ensure it is available on PATH."
        ) from exc

    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _require_beads_context() -> None:
    current = Path.cwd().resolve()

    for candidate in (current, *current.parents):
        beads_dir = candidate / ".beads"
        if beads_dir.is_dir():
            return

    raise BeadsNotInitializedError(
        "No .beads directory found in the current path. "
        "Run `bd init` at repository root or change into a Beads-initialized workspace."
    )
