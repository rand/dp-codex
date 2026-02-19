# Troubleshooting Guide

When something fails, use this page to triage quickly and recover without guesswork.

## Fast Triage Sequence

1. `git status`
2. `bd ready`
3. `make check`
4. `dp enforce pre-commit --policy dp-policy.json --json`
5. `dp enforce pre-push --policy dp-policy.json --json`

If you still do not have a clear cause, capture command output and continue below.

## `dp policy validate` reports missing policy file

Cause: `dp-policy.json` is missing or path is wrong.

Fix:

```bash
ls dp-policy.json
dp policy validate --config dp-policy.json
```

## `dp task ...` says no `.beads` directory exists

Cause: repo is not initialized for Beads.

Fix:

```bash
bd init -p <repo-prefix>
```

## `dp enforce ...` fails with `bd command not found`

Cause: `task_sync` is enabled by policy but Beads CLI is unavailable.

Fix:

1. Install `bd`, or
2. Disable `task_sync` in policy where appropriate.

## `dp enforce ...` fails with uv cache permission error

Cause: default uv cache location is not writable in this environment.

Fix:

```bash
export UV_CACHE_DIR=.uv-cache
dp enforce pre-commit --policy dp-policy.json
```

## Trace validation fails unexpectedly

Likely causes:

1. Missing `[SPEC-XX.YY]` declarations.
2. Trace markers referencing wrong IDs.
3. File globs not matching intended paths.

Fix:

```bash
dp trace validate --json --spec-glob 'docs/specs/**/*.md' --trace-glob 'dp/**/*.py'
dp trace coverage --json --spec-glob 'docs/specs/**/*.md' --trace-glob 'dp/**/*.py'
```

## Pre-push blocked by `worktree-dirty`

Cause: tracked or untracked changes remain while `dp review` expects a clean commit-ready state.

Fix:

1. Commit or stash changes.
2. Re-run:

```bash
dp review --json
dp enforce pre-push --policy dp-policy.json --json
```

## Verify outcome is `incomplete` or `failed`

Cause: manifest entries or artifact links are missing/inconsistent.

Fix:

1. Check `docs/verify/manifest.json` IDs and paths.
2. Ensure artifacts exist and are reachable from expected path roots.
3. Re-run `dp verify --json`.

## Emergency bypass path

Only use when operational risk justifies it:

```bash
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="incident mitigation" git push
```

Then:

1. File remediation work.
2. Restore normal checks.
3. Re-run enforcement and quality gates.

## Reporting A New Problem

Include:

1. Command executed.
2. Full stderr/stdout.
3. Relevant policy file snippet.
4. Repo state summary (`git status`, branch name, recent commit).

A good bug report should let another engineer reproduce the issue without telepathy.
