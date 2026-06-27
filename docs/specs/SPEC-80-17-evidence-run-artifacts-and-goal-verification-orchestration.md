# SPEC-80.17 Evidence Run Artifacts And Goal Verification Orchestration

Status: active
Issue: dpcx-pb5.14
Parent: SPEC-80

[SPEC-80.17]

## Intent

SPEC-80.08 made evidence execution deterministic and safe. SPEC-80.10 made successful evidence
advance a goal to `verified`. The remaining gap is operational: humans and agents still have to
capture `dp evidence run` stdout manually, choose evidence-run paths by convention, and remember the
exact sequence for goal verification.

This slice makes the evidence path first-class without weakening the gates:

1. `dp evidence run` can write a durable run artifact itself.
2. `dp verify --goal <goal.json> --json` orchestrates goal lint, evidence lint, evidence execution
   or artifact validation, and goal verification.
3. Goal handoffs include concrete evidence artifact paths and exact evidence/complete/verify
   commands.

The command remains deterministic and local. It does not call an LLM, synthesize evidence, run a
campaign loop, or treat agent narration as proof.

## Artifact Convention

The default evidence-run path for a goal is:

```text
docs/evidence-runs/RUN-<goal-id>.json
```

Example:

```text
docs/evidence-runs/RUN-GOAL-SPEC-70.01.json
```

The path is a mutable "latest run" convenience artifact. Verification events record the evidence
artifact hash at the time a goal is verified, so later overwrites are detectable by comparing the
event hash to the artifact. Overwrites require an explicit `--force`.

## Commands

```bash
dp evidence run <evidence.json> --output <run.json> --json
dp evidence run <evidence.json> --output <run.json> --force --json
dp verify --goal <goal.json> --json
dp verify --goal <goal.json> --evidence <run.json> --json
dp verify --goal <goal.json> --evidence-output <run.json> --force --json
```

Existing commands remain valid:

```bash
dp evidence run <evidence.json> --json
dp goal verify <goal.json> --evidence <run.json> --json
dp verify --manifest docs/verify/manifest.json --json
```

## Requirements

1. `dp evidence run --output` MUST validate the output path before executing checks.
2. Output paths MUST be sane relative JSON paths:
   1. no absolute paths;
   2. no `~`;
   3. no leading `-`;
   4. no `..` path parts;
   5. `.json` suffix required.
3. `dp evidence run --output` MUST refuse to overwrite an existing artifact unless `--force` is
   present.
4. If the output path is invalid or blocked by overwrite policy, no evidence check may execute.
5. When execution is attempted with `--output`, dp MUST write the evidence run payload to the
   requested path whether checks pass or fail.
6. The written payload MUST remain a `command == "evidence.run"` object consumable by
   `dp goal verify`.
7. The evidence run payload SHOULD include an `artifact` field with the written path when an output
   artifact is requested.
8. `dp verify --goal` MUST validate the GoalContract before executing or verifying evidence.
9. `dp verify --goal` MUST require a GoalContract `evidence.evidence_plan`.
10. `dp verify --goal` MUST lint the referenced EvidencePlan before running evidence or validating
    a supplied run artifact.
11. When `--evidence` is supplied, `dp verify --goal` MUST NOT run evidence; it validates the
    supplied artifact through the same deterministic goal verifier.
12. When `--evidence` is absent, `dp verify --goal` MUST run the referenced EvidencePlan through
    `dp evidence run`, write the result to `--evidence-output` or the default artifact path, and
    verify only if the evidence run succeeds.
13. `dp verify --goal` MUST append a `verified` goal event if and only if the existing
    `dp goal verify` evidence predicates pass.
14. `dp verify --goal` MUST include stable stage results for:
    1. goal lint;
    2. evidence lint;
    3. evidence run or supplied evidence artifact;
    4. trace/provenance summary;
    5. goal verification.
15. Goal, loop, campaign, and Codex handoff commands MUST include concrete evidence artifact paths
    instead of `<run.json>` placeholders when the GoalContract exposes an EvidencePlan.
16. Exit codes MUST be:
    1. `0` when goal verification succeeds.
    2. `1` when deterministic evidence or verification checks fail.
    3. `2` for malformed input, missing files, invalid output paths, overwrite refusal, unsupported
       schema, or incomplete orchestration input.

## Formal Invariants

Let `G` be a GoalContract, `P` the EvidencePlan referenced by `G.evidence.evidence_plan`, `A` an
evidence-run artifact path, `R(P)` the deterministic run result, and `V(G, A)` the existing
`dp goal verify` predicate.

1. Output preflight:
   `invalid(A) OR exists(A) without force => evidence checks executed = 0`.
2. Artifact fidelity:
   when `dp evidence run P --output A` executes, `json(A).command = "evidence.run"`.
3. No shell expansion:
   this slice does not alter SPEC-80.08's argv-only, `shell=False`, registered-command executor.
4. Supplied evidence mode:
   `dp verify --goal G --evidence A` executes zero EvidencePlan checks.
5. Fresh evidence mode:
   `dp verify --goal G` verifies `A` only after `R(P).ok = true`.
6. Verification equivalence:
   `dp verify --goal G --evidence A` appends `verified` exactly when `dp goal verify G --evidence A`
   would append `verified`.
7. No self-report proof:
   if `json(A).command != "evidence.run"`, orchestration fails before `verified`.

## Non-Goals

1. No cryptographic signing or tamper-proof storage.
2. No immutable evidence history beyond append-only goal events in this slice.
3. No model-based interpretation of evidence.
4. No background campaign runner.
5. No raw shell execution or command discovery.

## Verification

Required checks:

```bash
pytest tests/test_evidence_artifacts_and_verify.py tests/test_evidence_run.py tests/test_goal_state.py
pytest tests/test_goal_emit.py tests/test_loop_ledger.py tests/test_campaign_recovery.py
make check
dp trace validate --json
dp trace coverage --json
```
