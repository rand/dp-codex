# Verify Workflow Runbook

`dp verify` evaluates goal-backward evidence using three levels:

1. `truths`
2. `artifacts`
3. `links`

## Manifest Format

Default manifest path: `docs/verify/manifest.json`

```json
{
  "truths": [{"id": "T1", "verified": true}],
  "artifacts": [{"id": "A1", "path": "artifacts/proof.txt"}],
  "links": [{"truth_id": "T1", "artifact_id": "A1"}]
}
```

## Outcomes and Exit Codes

1. `verified` -> exit `0`
2. `incomplete` -> exit `2`
3. `failed` -> exit `1`

## Commands

```bash
dp verify
dp verify --manifest docs/verify/manifest.json --json
```
