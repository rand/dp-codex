# Goal Workflow Runbook

Goal commands are the first SPEC-80 control-plane surface. They let Codex operate a bounded
GoalContract through dp without relying on chat memory.

## What Exists Now

1. `dp goal lint`: deterministic GoalContract validation.
2. `dp goal status`: state reconstruction from `.dp/goals/events.jsonl`.
3. `dp goal claim/start/heartbeat/block/release`: append-only lifecycle events.
4. `dp goal complete`: records an evidence path as `evidence_pending`; it does not verify success.
5. `dp goal verify`: verifies a matching successful evidence run and records `verified`.
6. `dp goal block --write-artifact`: resolves GoalContract blocker routes into spec, ADR, or
   EvidencePlan stubs and optional Beads follow-ups.
7. `dp goal emit` and `dp agent prompt`: Codex-operable prompt emission from a valid contract.
8. `dp evidence lint`: deterministic EvidencePlan validation without command execution.
9. `dp evidence run`: controlled execution of linted registered checks with typed assertions.
10. `dp loop lint/status/next`: deterministic LoopLedger validation, state reconstruction, and
   next-goal packaging.
11. `dp campaign lint/status/recover`: deterministic CampaignManifest validation and recovery from
   repo artifacts plus append-only goal and campaign events.
12. `dp campaign init --primary-spec <path> --write`: conservative draft scaffold generation plus
   deterministic semantic-signal extraction from a local primary spec.
13. `dp campaign refine <campaign.json> --write`: deterministic authoring refinement into child
    spec/ADR stubs, GoalContract/EvidencePlan refinement metadata, and optional Beads
    epics/issues.
14. `dp campaign refine <campaign.json> --llm`: agent-mediated LLM refinement request emission.
15. `dp campaign refine <campaign.json> --llm-response <response.json> --write`: deterministic
    import of model-authored draft refinement metadata.
16. `dp campaign run <campaign.json> --driver codex --supervised`: one-step supervised handoff
    that validates campaign state, claims one ready goal, emits the Codex package, and stops.

## What Does Not Exist Yet

1. Richer semantic graph hardening beyond the response import metadata.
2. Direct Codex process launch.
3. Background or multi-goal autonomous campaign running.

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
dp goal block docs/goals/GOAL-example.json --reason needs_decision --write-artifact --json
```

Known block reasons are:

1. `needs_specification`
2. `needs_decision`
3. `needs_validator`
4. `unsafe_scope`
5. `budget_exhausted`

Use `--write-artifact` when a blocked route should create the next process artifact. Supported
route actions are:

1. `create_spec_stub`: writes `docs/specs/BLOCKER-<goal>-<reason>.md`.
2. `create_adr_stub`: writes a proposal ADR under `docs/adr/`.
3. `create_evidence_stub`: writes a lintable EvidencePlan JSON under `docs/evidence/`.

If the GoalContract route has `also_create_beads_issue: true`, dp attempts a Beads follow-up with
`bd create ... --json`. Beads failures are reported in JSON and recorded in the blocked event; they
do not erase the blocked state or any written artifact.

If the agent session resets or the work should be released:

```bash
dp goal release docs/goals/GOAL-example.json --reason "context reset" --json
```

## Record Evidence

When an evidence plan exists, lint it before recording or relying on evidence:

```bash
dp evidence lint docs/evidence/EVIDENCE-example.json --json
mkdir -p docs/evidence-runs
dp evidence run docs/evidence/EVIDENCE-example.json --json > docs/evidence-runs/RUN-example.json
```

```bash
dp goal complete docs/goals/GOAL-example.json --evidence docs/evidence-runs/RUN-example.json --json
dp goal verify docs/goals/GOAL-example.json --evidence docs/evidence-runs/RUN-example.json --json
```

`complete` records `evidence_pending`. `verify` records `verified` only when the run output was
emitted by `dp evidence run`, the run passed, the goal id matches, the evidence plan path matches
the GoalContract, and the current EvidencePlan hash matches the run.

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
success from agent narration. It also summarizes `.dp/campaigns/events.jsonl` and emits a `resume`
object with one of these actions:

1. `resume_claimed_goal`
2. `verify_evidence`
3. `resolve_blocker`
4. `claim_next_goal`
5. `campaign_verified`
6. `no_ready_work`

## Run One Supervised Campaign Step

When a campaign has a current loop, ask dp to prepare exactly one Codex handoff:

```bash
dp campaign run docs/campaigns/CAMPAIGN-example.json --driver codex --supervised --json
```

The returned `next` object is the same package produced by `dp loop next --claim --emit codex`.
It includes the Codex `/goal`, read-first paths, evidence plan, lease, allowed paths, and lifecycle
commands for `start`, `heartbeat`, `complete`, `verify`, `block`, and `release`.

If the current loop already has an active non-stale claim, `campaign run` returns a
`campaign.resume` package for that goal instead of claiming another node. If it does claim a new
goal, it appends a `handoff_claimed` event to `.dp/campaigns/events.jsonl`.

This command is supervised by design. It claims at most one ready goal and exits. It does not launch
Codex, run evidence, verify the goal, or continue to another node. Use the emitted lifecycle
commands to operate the claimed goal, then call `dp campaign run` again when the campaign is ready
for another handoff.

## Scaffold From A Primary Spec

For a local primary spec, create a draft campaign shell:

```bash
dp campaign init --primary-spec docs/primary/example.md --write --json
```

The command writes a CampaignManifest, LoopLedger, draft GoalContracts, EvidencePlan stubs, and a
`needs_refinement` marker. It also emits a `compiler` object with deterministic requirement,
evidence, decision, blocker, and dependency cues for each generated node. Generated artifacts are
linted, but the campaign remains `draft`: dependency cues are not inferred edges, and the command
does not author child specs, ADRs, validators, Beads issues, or verified work.

## Refine A Draft Campaign

For a generated draft campaign, inspect planned refinement without writing:

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --json
```

Write deterministic child spec/ADR stubs and GoalContract/EvidencePlan refinement metadata:

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --json
```

Materialize Beads work only when explicitly requested:

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --create-beads --json
```

Emit an LLM refinement request for the calling agent's current provider/model:

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --llm --json
```

After the calling agent writes a response artifact, import it through deterministic validation:

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --llm-response response.json --write --json
```

Refinement is still authoring, not verification. It keeps the campaign `draft`, does not execute
evidence, and does not infer dependency edges from prose. LLM-assisted response import records
provider/model provenance and rejects unknown goals, prompt-hash mismatches, unsafe paths, and raw
shell evidence proposals. Deterministic gates remain responsible for readiness and completion.

## Safe Local Smoke Test

Use the checked-in fixture when you want to verify the command surface without writing events:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
dp goal emit tests/fixtures/goals/valid_spec_70_01.json --format codex --json
dp evidence run tests/fixtures/evidence/valid_run_goal_lint.json --json
dp loop next tests/fixtures/loops/valid_spec_80_04.json --emit codex --json
dp campaign recover tests/fixtures/campaigns/valid_spec_80_06.json --json
```
