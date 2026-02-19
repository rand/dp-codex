# Environment Bootstrap Runbook

Use this runbook to get a new machine or a fresh Codex session ready for development.

## Prerequisites

1. `git`
2. `python3` (3.11+)
3. `uv` (<https://docs.astral.sh/uv/getting-started/installation/>)
4. `bd` (Beads CLI)
5. `make`

## First-Time Setup

1. Enter the repository root:

```bash
cd /path/to/dp-codex
```

2. Install project tooling and test dependencies:

```bash
uv sync --dev
```

3. Confirm Beads is healthy and work is discoverable:

```bash
bd ready
```

4. Run the canonical quality gates:

```bash
make check
```

If `make check` passes, your environment is ready.

## Codex Session Startup

At the start of each implementation session:

```bash
bd ready
bd update <issue-id> --status in_progress
```

Use `bd show <issue-id>` to confirm acceptance criteria before editing.

## Troubleshooting

`uv` cache permission error in sandboxed environments:

```bash
UV_CACHE_DIR=.uv-cache make check
```

`bd` command not found:

1. Ensure Beads CLI is installed and on `PATH`.
2. Confirm you are inside the repository root with `.beads/`.

`make` target missing:

1. Run `git pull` to get latest `Makefile` updates.
2. Check available targets:

```bash
make -pRrq | rg -n '^[a-zA-Z0-9_.-]+:'
```
