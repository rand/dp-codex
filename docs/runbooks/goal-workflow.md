# Goal Workflow Runbook

Goal commands are the first SPEC-80 control-plane surface. They let Codex operate a bounded
GoalContract through dp without relying on chat memory.

## What Exists Now

1. `dp goal lint`: deterministic GoalContract validation.
2. `dp goal status`: state reconstruction from `.dp/goals/events.jsonl`.
3. `dp goal claim/start/heartbeat/block/release`: append-only lifecycle events.
4. `dp goal complete`: records an evidence path as `evidence_pending`; it does not verify success.
5. `dp goal emit` and `dp agent prompt`: Codex-operable prompt emission from a valid contract.
6. `dp evidence lint`: deterministic EvidencePlan validation without command execution.

## What Does Not Exist Yet

1. `dp loop next`.
2. `dp evidence run`.
3. `dp campaign init/status/recover`.
4. LLM-assisted campaign refinement.
5. A supervised campaign runner.

Those are tracked as SPEC-80 follow-up issues.

## Validate A Goal

Replace `docs/goals/GOAL-example.json` with the path to the contract you are operating.

```bash
dp goal lint docs/goals/GOAL-example.json --json
```

Exit codes:

1. `0`: valid.
2. `1`: loaded JSON, but invalid contract.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete input.

## Operate A Goal

```bash
dp goal claim docs/goals/GOAL-example.json --agent codex --lease 2h --json
dp goal start docs/goals/GOAL-example.json --agent codex --json
dp goal heartbeat docs/goals/GOAL-example.json --json
```

If blocked:

```bash
dp goal block docs/goals/GOAL-example.json --reason needs_decision --json
```

Known block reasons are:

1. `needs_specification`
2. `needs_decision`
3. `needs_validator`
4. `unsafe_scope`
5. `budget_exhausted`

If the agent session resets or the work should be released:

```bash
dp goal release docs/goals/GOAL-example.json --reason "context reset" --json
```

## Record Evidence

When an evidence plan exists, lint it before recording or relying on evidence:

```bash
dp evidence lint docs/evidence/EVIDENCE-example.json --json
```

```bash
dp goal complete docs/goals/GOAL-example.json --evidence docs/evidence-runs/RUN-example.json --json
```

This records `evidence_pending`. It intentionally does not mark the goal verified because the
evidence executor and goal-verification integration are future work.

## Emit A Codex Prompt

```bash
dp goal emit docs/goals/GOAL-example.json --format codex --json
dp agent prompt --goal docs/goals/GOAL-example.json --format codex --json
```

The emitted prompt includes the objective, evidence cues, boundaries, iteration policy, blocked
condition, and lifecycle commands. Emission does not call an LLM and does not execute evidence.

## Safe Local Smoke Test

Use the checked-in fixture when you want to verify the command surface without writing events:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
dp goal emit tests/fixtures/goals/valid_spec_70_01.json --format codex --json
```
