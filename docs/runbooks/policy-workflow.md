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
