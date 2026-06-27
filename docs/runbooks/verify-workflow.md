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

Legacy artifact records only need `id` and `path`; this remains supported. For stronger campaign
evidence, an artifact can also record content hash, command outcome, Beads issue, and spec
provenance:

```json
{
  "truths": [{"id": "T1", "verified": true}],
  "artifacts": [
    {
      "id": "A1",
      "path": "docs/evidence-runs/RUN-GOAL-example.json",
      "sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "command": {
        "argv": ["dp", "evidence", "run", "docs/evidence/EVIDENCE-example.json", "--json"],
        "exit_code": 0,
        "success_exit_codes": [0],
        "cwd": "."
      },
      "task_id": "dpcx-ea9.3",
      "spec_id": "SPEC-70.04"
    }
  ],
  "links": [{"truth_id": "T1", "artifact_id": "A1"}]
}
```

Structured fields are opt-in but enforced when present:

1. `sha256` must match the artifact bytes.
2. `command` must be a recorded object with `argv`, `exit_code`, and `success_exit_codes`.
3. `command.exit_code` must be listed in `command.success_exit_codes`.
4. `command` must not be a shell string.
5. `task_id` and `spec_id` must look like local Beads and spec identifiers.

`dp verify --manifest` never executes commands from manifest JSON. Command records describe evidence
already produced by a human, CI job, agent, or `dp evidence run`.

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
