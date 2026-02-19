# Troubleshooting Guide

## `dp policy validate` fails with "Policy file not found"

Cause: `dp-policy.json` is missing or wrong path.

Fix:

```bash
ls dp-policy.json
dp policy validate --config dp-policy.json
```

## `dp task ...` fails with "No .beads directory found"

Cause: repository has not been initialized for Beads.

Fix:

```bash
bd init -p <repo-prefix>
```

## `dp enforce ...` fails with `bd command not found`

Cause: strict policy enables `task_sync` but Beads CLI is missing.

Fix:

1. Install `bd`, or
2. Set policy override `"task_sync": false` for guided/minimal workflows.

## `dp enforce ...` fails with `Failed to initialize cache`

Cause: `uv` cache path is not writable in the current environment.

Fix:

```bash
export UV_CACHE_DIR=.uv-cache
dp enforce pre-commit --policy dp-policy.json
```

## Pre-push blocked by `worktree-dirty`

Cause: tracked/untracked changes exist during `dp review`.

Fix:

1. Commit or stash changes.
2. Re-run:

```bash
dp review --json
dp enforce pre-push --policy dp-policy.json --json
```

## Emergency path needed immediately

Use one-time bypass with explicit reason:

```bash
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="incident mitigation" git push
```

Then perform follow-up remediation and normal enforcement checks.
