# Decompose Workflow Runbook

`dp decompose` emits a DAG-validated execution plan with configurable context windows.

## Inputs

1. Explicit items via repeated `--item`
2. Fallback from discovered spec IDs via `--spec-glob` (default: `docs/specs/**/*.md`)

## Context Window Control

Use `--context-window <tokens>` to constrain per-node estimated token budgets.
Large items are split into sequential sub-nodes when estimates exceed the configured window.

Codex presets:

1. `codex-small` -> `32000`
2. `codex-medium` -> `64000`
3. `codex-large` -> `128000`

Use `--preset <name>` to select a preset without manually setting token counts.

## Heuristics

1. Token estimate baseline uses word-count scaling with a minimum floor.
2. Oversized items are split into ordered sub-nodes.
3. Adjacent tiny items are merged before splitting to avoid overly granular plans.

## Commands

```bash
dp decompose --item "Implement parser" --item "Add tests" --context-window 4096
dp decompose --item "Implement parser" --preset codex-medium
dp decompose --json
```
