# Policy Workflow Runbook

Enforcement behavior is controlled by `dp-policy.json`.

## Schema

The policy schema is versioned at:

1. `docs/schemas/policy.schema.json`

Supported modes:

1. `strict`
2. `guided`
3. `minimal`

Per-check overrides use boolean values in `overrides`.

Supported checks:

1. `lint`
2. `typecheck`
3. `tests`
4. `trace_validate`
5. `trace_coverage`
6. `task_health`
7. `review`
8. `verify`

`task_sync` remains accepted as a deprecated compatibility override and maps to
`task_health` when `task_health` is not set explicitly.

## Example

```json
{
  "mode": "guided",
  "overrides": {
    "review": true,
    "verify": false
  }
}
```

## Validate

```bash
dp policy validate --config dp-policy.json
dp policy validate --config dp-policy.json --json
```

## Execute Enforcement

```bash
dp enforce pre-commit --policy dp-policy.json
dp enforce pre-push --policy dp-policy.json
dp enforce pre-push --policy dp-policy.json --json
```

## Emergency Bypass

Bypass is only for urgent production or recovery scenarios.

```bash
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="incident rollback" git commit
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="incident rollback" git push
```

Each bypass appends one JSON line to `.dp/bypass-log.jsonl` with UTC timestamp, stage, actor, and reason.
