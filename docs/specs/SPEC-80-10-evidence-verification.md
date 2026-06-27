# SPEC-80.10 Evidence Verification To Goal Completion

Status: active
Issue: dpcx-pb5.10
Parent: SPEC-80

[SPEC-80.10]

## Intent

dp can now lint and run EvidencePlans, but campaign progress still stops at
`evidence_pending`. A campaign control plane needs a deterministic transition from an evidence run
artifact to a verified goal state, without trusting agent narration or arbitrary JSON.

This slice adds a manual verification command over existing artifacts. It does not run evidence
implicitly, synthesize campaigns, call an LLM, or supervise agent loops.

## Command

```bash
dp goal verify <goal.json> --evidence <run.json> --json
```

## Requirements

1. `dp goal verify` MUST validate the GoalContract before reading evidence.
2. The evidence path MUST be a sane relative path to an existing JSON object.
3. The evidence object MUST be a `dp evidence run` output, not an agent-authored success note.
4. The evidence run MUST be successful:
   1. `command == "evidence.run"`
   2. `ok == true`
   3. `error == null`
   4. every check has `ok == true` and `status == "passed"`
   5. every typed assertion has `ok == true`
   6. summary counts match the check results
5. The evidence run `goal_id` MUST match the GoalContract id.
6. The evidence run `evidence_id` MUST match the linted EvidencePlan id.
7. The evidence run MUST record its source EvidencePlan path and sha256.
8. The source EvidencePlan path MUST match `goal.evidence.evidence_plan`.
9. The current EvidencePlan file MUST still exist, lint successfully, match the GoalContract id,
   and hash to the same sha256 recorded in the evidence run.
10. On success, dp MUST append a `verified` event to `.dp/goals/events.jsonl`.
11. On failure, dp MUST append no event.
12. Exit codes MUST be:
    1. `0` when the goal is verified.
    2. `1` when the evidence run is loaded but fails deterministic verification.
    3. `2` for malformed input, missing files, unsupported evidence-run shape, invalid paths, or
       incomplete verification input.

## Formal Invariants

Let `G` be a valid GoalContract, `P` the EvidencePlan referenced by
`G.evidence.evidence_plan`, `R` a `dp evidence run` artifact, and `H(P)` the current plan hash.

1. No self-report proof:
   `R.command != "evidence.run" => verify(G, R) = input_error`.
2. Goal match:
   `R.goal_id != G.id => verify(G, R) = evidence_failure`.
3. Plan closure:
   `R.evidence_plan.path != G.evidence.evidence_plan => verify(G, R) = evidence_failure`.
4. Freshness:
   `R.evidence_plan.sha256 != H(P) => verify(G, R) = evidence_failure`.
5. Evidence success:
   `exists check in R.checks where check.ok != true => verify(G, R) = evidence_failure`.
6. Deterministic transition:
   a `verified` event is appended if and only if all predicates above pass.
7. Loop unlock:
   loop dependencies unlock only from reconstructed `verified` goal state, not from
   `evidence_pending`, failed evidence, or agent narration.

## Non-Goals

1. No cryptographic signing or tamper-proof run storage in this slice.
2. No automatic evidence execution from `dp goal verify`.
3. No LLM judgment.
4. No background runner.
5. No campaign-level completion inference beyond existing loop state reconstruction.

## Verification

Required evidence for this slice:

```bash
pytest tests/test_goal_state.py tests/test_goal_emit.py tests/test_evidence_run.py
make check
dp trace validate --json
dp trace coverage --json
```
