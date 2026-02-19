# Progress Workflow Runbook

`dp progress` writes one-shot progress snapshots to Markdown and JSON, and can evaluate watch triggers.

## Commands

```bash
dp progress
dp progress --output-dir docs/progress --json
dp progress --watch --json
```

## Outputs

Each run writes:

1. `progress-<timestamp>.json`
2. `progress-<timestamp>.md`

Reports include an `Agent Bootstrap` section with concise summary metrics, triggered checks, and prioritized next commands for fresh Codex sessions.

## Watch Mode Triggers

Current trigger set:

1. `working-tree-dirty`
2. `ready-issue-growth` (requires previous snapshot)
3. `spec-count-change` (requires previous snapshot)

Watch mode returns non-zero when one or more triggers fire.
