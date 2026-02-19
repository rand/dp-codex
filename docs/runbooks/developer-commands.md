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

Run policy-driven enforcement checks directly:

```bash
uv run dp enforce pre-commit --policy dp-policy.json
uv run dp enforce pre-push --policy dp-policy.json
```

## CI Guidance

CI should execute:

1. `make check`
2. `uv run dp enforce pre-commit --policy dp-policy.json --json`
3. `uv run dp enforce pre-push --policy dp-policy.json --json`

This keeps hook behavior and CI behavior aligned against the same versioned policy file.
