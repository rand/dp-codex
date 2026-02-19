# Developer Command Runbook

This repository uses `make` as the single command surface for quality gates.

## Prerequisites

1. Install `uv`: <https://docs.astral.sh/uv/getting-started/installation/>
2. Install dev dependencies:

```bash
uv sync --dev
```

## Quality Gates

Run all gates:

```bash
make check
```

Run individual gates:

```bash
make test
make lint
make typecheck
make format
```

## CI Guidance

CI should execute the same `make` targets (at minimum `make check`) to keep local and remote validation aligned.
