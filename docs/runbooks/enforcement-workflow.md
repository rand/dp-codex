# Enforcement Workflow Runbook

This runbook defines how local hooks and CI enforce repository policy.

## Policy Source of Truth

1. Policy file: `dp-policy.json`
2. Validation command: `uv run dp policy validate --config dp-policy.json`
3. Default mode in this repository: `guided` with explicit overrides for `review` and `verify`

## Check Groups

Pre-commit checks:

1. `lint`
2. `typecheck`
3. `tests`
4. `trace_validate`
5. `trace_coverage` (fails when uncovered specs are present)

Pre-push checks:

1. `task_sync`
2. `review`
3. `verify`

## Install Hooks

```bash
./hooks/install.sh
```

This installs `hooks/pre-commit` and `hooks/pre-push` into `.git/hooks/`.

## Manual Enforcement Invocation

```bash
uv run dp enforce pre-commit --policy dp-policy.json
uv run dp enforce pre-push --policy dp-policy.json
```

For automation consumers:

```bash
uv run dp enforce pre-push --policy dp-policy.json --json
```

## Bypass Protocol

Use bypass only for emergency fixes where normal gates are unsafe or unavailable.

1. Set `DP_BYPASS_ENFORCEMENT=1`
2. Provide `DP_BYPASS_REASON` with a concrete incident rationale
3. Perform the single blocked action
4. Follow up with remediation and a normal enforcement pass

Example:

```bash
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="restore service after failed deploy" git push
```

Audit log:

1. File: `.dp/bypass-log.jsonl`
2. One JSON object per bypass
3. Fields: `timestamp_utc`, `stage`, `actor`, `reason`
