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
dp doctor --json
bd ready --json
```

4. Run the canonical quality gates:

```bash
make check
```

5. Install git hook enforcement scripts:

```bash
./hooks/install.sh
```

If all commands pass, your environment is ready.

## Codex Session Startup

At the start of each implementation session:

```bash
dp doctor --json
bd ready --claim --json
```

If you already know the issue ID, use `bd update <issue-id> --claim`. Use
`bd show <issue-id>` to confirm acceptance criteria before editing.

## Troubleshooting

`uv` cache permission error in sandboxed environments:

```bash
UV_CACHE_DIR=.uv-cache make check
```

`bd` command not found:

1. Ensure Beads CLI is installed and on `PATH`.
2. Confirm you are inside the repository root with `.beads/`.

Beads database exists but is not usable:

```bash
bd bootstrap --dry-run
dp doctor --json
```

If `dp doctor` reports missing `issue_prefix` on an empty embedded database,
recover from the tracked issue snapshot:

```bash
bd init --reinit-local --prefix <prefix>
bd import .beads/issues.jsonl
```

`make` target missing:

1. Run `git pull` to get latest `Makefile` updates.
2. Check available targets:

```bash
make -pRrq | rg -n '^[a-zA-Z0-9_.-]+:'
```
