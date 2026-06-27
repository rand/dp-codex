# Developer Command Runbook

This repository uses `make` as the command surface for quality gates and `dp` for workflow checks.

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

## Typical Daily Sequence

```bash
dp doctor --json
bd ready --claim --json
make check
uv run dp enforce pre-commit --policy dp-policy.json --json
```

When a task is represented by a GoalContract, validate and operate it through dp:

```bash
dp goal lint docs/goals/GOAL-example.json --json
dp evidence lint docs/evidence/EVIDENCE-example.json --json
dp goal claim docs/goals/GOAL-example.json --agent codex --lease 2h --json
dp goal start docs/goals/GOAL-example.json --agent codex --json
```

Before push:

```bash
uv run dp review --json
uv run dp verify --json
uv run dp enforce pre-push --policy dp-policy.json --json
bd --readonly status --json
```

## Related Guides

1. `/docs/guides/quickstart-first-feature.md`
2. `/docs/guides/feature-driver-playbook.md`
3. `/docs/runbooks/goal-workflow.md`
4. `/docs/reference/cli-workflow-reference.md`
