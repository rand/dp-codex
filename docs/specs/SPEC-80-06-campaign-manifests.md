# SPEC-80.06 Campaign Manifests

Status: active
Issue: dpcx-pb5.6
Parent: SPEC-80

[SPEC-80.06]

## Intent

dp must make an agent campaign recoverable from repository artifacts before it can compile primary
specs or run evidence. A CampaignManifest is the durable index that binds one primary spec to the
repo-owned specs, ADRs, GoalContracts, EvidencePlans, LoopLedgers, and Beads references that make up
the campaign.

This slice only validates manifests and reconstructs visible state. It does not synthesize campaign
plans, execute evidence, call an LLM, or run agent loops.

## Contract

A valid CampaignManifest:

1. Is a JSON object with `schema_version: "0.1"`.
2. Has an id matching `CAMPAIGN-*` and a non-empty title.
3. Declares a `primary_spec.path` that is a sane relative path to an existing file.
4. Declares an `artifacts` object with non-empty `goals` and `loops` arrays.
5. Declares any specs, ADRs, goals, evidence plans, and loop ledgers as sane relative paths.
6. Contains no duplicate artifact paths.
7. References only valid GoalContracts from `artifacts.goals`.
8. References only valid EvidencePlans from `artifacts.evidence_plans`.
9. References only valid LoopLedgers from `artifacts.loops`.
10. Ensures every loop node goal path is declared in `artifacts.goals`.
11. Ensures every loop node evidence plan path, when present, is declared in
    `artifacts.evidence_plans`.
12. Declares `state.status` as one of `draft`, `ready`, `active`, `blocked`, `verified`, or
    `abandoned`.
13. Declares `state.current_loop` as the id of a declared loop.
14. Does not treat `evidence_pending` or agent narration as verified completion.

## Commands

```bash
dp campaign lint <campaign.json> --json
dp campaign status <campaign.json> --json
dp campaign recover <campaign.json> --json
```

Exit codes:

1. `0`: valid manifest, successful status, or successful recovery.
2. `1`: loaded manifest is invalid, or recovery found missing/invalid campaign artifacts.
3. `2`: missing manifest file, malformed JSON, non-object JSON, unsupported schema, or unsupported
   command input.

## Formal Invariants

Let `M` be a CampaignManifest, `L(M)` the set of loop ledgers named by
`M.artifacts.loops`, `G(M)` the set of GoalContracts named by `M.artifacts.goals`,
`E(M)` the set of EvidencePlans named by `M.artifacts.evidence_plans`, and `S(log)` the state
reconstructed from `.dp/goals/events.jsonl`.

1. Artifact closure: for every loop node `n` in every `l in L(M)`, `n.goal_path in G(M)`.
2. Evidence closure: for every loop node evidence path `p`, if `p` is present then `p in E(M)`.
3. Deterministic recovery: `recover(M, log)` is a pure function of `M`, declared artifacts, and
   `log`; it does not consult chat history, hidden state, LLMs, network services, or shell output.
4. Conservative completion: a campaign is derived as `verified` only when loop status reports every
   node verified. `evidence_pending` is not proof.
5. No execution: `lint`, `status`, and `recover` read and validate artifacts but never execute
   evidence commands.

## Non-Goals

1. No `dp campaign init`.
2. No primary-spec decomposition or semantic campaign planning.
3. No evidence execution.
4. No LLM-assisted refinement.
5. No supervised or autonomous runner.

## Verification

Required evidence for this slice:

```bash
dp campaign lint tests/fixtures/campaigns/valid_spec_80_06.json --json
dp campaign status tests/fixtures/campaigns/valid_spec_80_06.json --json
dp campaign recover tests/fixtures/campaigns/valid_spec_80_06.json --json
pytest tests/test_campaign_manifest.py
make check
```
