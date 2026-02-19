# Review Workflow Runbook

Use `dp review` to run deterministic, local checklist checks before commit/push.

## Checks

Blocking checks:

1. Dirty worktree detection from `git status --porcelain`
2. Merge conflict marker scan (`<<<<<<<`, `=======`, `>>>>>>>`)

Advisory checks:

1. Deferred-work marker scan (`TO` + `DO` and `FIX` + `ME`) in tracked text files

## Commands

```bash
dp review
dp review --json
```

Exit behavior:

1. Exit `0` when no blocking findings
2. Exit `1` when one or more blocking findings exist
