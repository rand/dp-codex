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
7. `dp evidence run`: controlled execution of linted registered checks with typed assertions.
8. `dp loop lint/status/next`: deterministic LoopLedger validation, state reconstruction, and
   next-goal packaging.
9. `dp campaign lint/status/recover`: deterministic CampaignManifest validation and recovery from
   repo artifacts plus append-only goal events.
10. `dp campaign init --primary-spec <path> --write`: conservative draft scaffold generation from a
   local primary spec.

## What Does Not Exist Yet

1. Semantic primary-spec campaign compilation.
2. LLM-assisted campaign refinement.
3. Verified evidence-to-goal completion.
4. A supervised campaign runner.

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
dp evidence run docs/evidence/EVIDENCE-example.json --json
```

```bash
dp goal complete docs/goals/GOAL-example.json --evidence docs/evidence-runs/RUN-example.json --json
```

This records `evidence_pending`. It intentionally does not mark the goal verified because the
goal-verification integration is future work.

## Emit A Codex Prompt

```bash
dp goal emit docs/goals/GOAL-example.json --format codex --json
dp agent prompt --goal docs/goals/GOAL-example.json --format codex --json
```

The emitted prompt includes the objective, evidence cues, boundaries, iteration policy, blocked
condition, and lifecycle commands. Emission does not call an LLM and does not execute evidence.

## Choose The Next Loop Goal

When a campaign has a LoopLedger, validate it and ask dp for the next ready goal:

```bash
dp loop lint docs/loops/LOOP-example.json --json
dp loop status docs/loops/LOOP-example.json --json
dp loop next docs/loops/LOOP-example.json --claim --emit codex --json
```

`next` skips blocked nodes and active claims. Dependencies unlock only when dependency goal state is
verified; `evidence_pending` remains evidence recorded, not proof of completion.

## Recover Campaign State

When a repository has a CampaignManifest, validate it and recover visible campaign state before
continuing work:

```bash
dp campaign lint docs/campaigns/CAMPAIGN-example.json --json
dp campaign status docs/campaigns/CAMPAIGN-example.json --json
dp campaign recover docs/campaigns/CAMPAIGN-example.json --json
```

`recover` reads the manifest, declared artifacts, loop ledgers, goal contracts, evidence plans, and
`.dp/goals/events.jsonl`. It does not use chat history, call an LLM, execute evidence, or infer
success from agent narration.

## Scaffold From A Primary Spec

For a local primary spec, create a draft campaign shell:

```bash
dp campaign init --primary-spec docs/primary/example.md --write --json
```

The command writes a CampaignManifest, LoopLedger, draft GoalContracts, EvidencePlan stubs, and a
`needs_refinement` marker. Generated artifacts are linted, but the campaign remains `draft` because
the command does not perform semantic planning.

## Safe Local Smoke Test

Use the checked-in fixture when you want to verify the command surface without writing events:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
dp goal emit tests/fixtures/goals/valid_spec_70_01.json --format codex --json
dp evidence run tests/fixtures/evidence/valid_run_goal_lint.json --json
dp loop next tests/fixtures/loops/valid_spec_80_04.json --emit codex --json
dp campaign recover tests/fixtures/campaigns/valid_spec_80_06.json --json
```
