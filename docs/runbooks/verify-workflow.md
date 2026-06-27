# Verify Workflow Runbook

`dp verify` has two deterministic modes.

1. Legacy manifest verification.
2. Goal evidence orchestration.

## Manifest Verification

Without `--goal`, `dp verify` evaluates goal-backward evidence using three levels:

1. `truths`
2. `artifacts`
3. `links`

### Manifest Format

Default manifest path: `docs/verify/manifest.json`

```json
{
  "truths": [{"id": "T1", "verified": true}],
  "artifacts": [{"id": "A1", "path": "artifacts/proof.txt"}],
  "links": [{"truth_id": "T1", "artifact_id": "A1"}]
}
```

### Outcomes and Exit Codes

1. `verified` -> exit `0`
2. `incomplete` -> exit `2`
3. `failed` -> exit `1`

### Commands

```bash
dp verify
dp verify --manifest docs/verify/manifest.json --json
```

## Goal Evidence Orchestration

With `--goal`, `dp verify` runs the agent-campaign evidence path for one GoalContract:

```bash
dp verify --goal docs/goals/GOAL-example.json --json
dp verify --goal docs/goals/GOAL-example.json \
  --evidence-output docs/evidence-runs/RUN-GOAL-example.json --force --json
dp verify --goal docs/goals/GOAL-example.json \
  --evidence docs/evidence-runs/RUN-GOAL-example.json --json
```

The command stages are:

1. goal lint;
2. EvidencePlan lint;
3. evidence execution to `docs/evidence-runs/RUN-<goal-id>.json`, unless `--evidence` supplies an
   existing run artifact;
4. trace/provenance summary from the GoalContract;
5. goal verification through the same deterministic predicate as `dp goal verify`.

Exit codes:

1. `0`: goal verified and a `verified` event was appended.
2. `1`: evidence or goal verification failed deterministically.
3. `2`: malformed input, missing files, invalid output path, overwrite refusal, or incomplete goal
   verification input.

`dp verify --goal` does not call an LLM, does not accept self-report JSON as proof, and does not
run inside hooks or CI unless explicitly invoked.
