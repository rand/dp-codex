# SPEC-80.19 End-To-End Human And Agent Campaign Pilot

Status: active
Issue: dpcx-pb5.16
Parent: SPEC-80

[SPEC-80.19]

## Intent

SPEC-80 is only useful if a human or Codex-like agent can operate a real campaign without relying on
chat memory. This pilot proves the current control-plane path against a realistic primary spec that
is not about dp-codex internals.

The pilot is not a benchmark for autonomous coding quality. It is a deterministic product proof for
the control plane:

1. primary spec intake;
2. campaign scaffold;
3. refinement artifacts;
4. Beads materialization;
5. next-goal handoff;
6. evidence artifact production;
7. goal verification;
8. blocker routing;
9. campaign recovery;
10. stable operator-facing summary.

## Scenario

The fixture project is a small "Field Report CLI" product. Its primary spec asks for a tool that
normalizes field observations into JSON, validates required fields, and reports operator-friendly
errors.

The subject matter is deliberately outside dp internals so the pilot exercises dp as a process
driver for an arbitrary project, not just for improving itself.

## User Journeys

### Human Operator

1. Provide a primary spec.
2. Run `dp campaign init --primary-spec ... --write --json`.
3. Run `dp campaign refine ... --write --create-beads --json`.
4. Inspect the generated campaign, child specs, ADRs, goals, evidence plans, loop ledger, and Beads
   issue ids.
5. Run `dp campaign run ... --driver codex --supervised --json` to get the first handoff.
6. Run `dp verify --goal ... --json` to produce evidence and verify the first goal.
7. Run `dp campaign recover ... --json` to see the next deterministic action.

### Agent Operator

1. Receive the supervised handoff package.
2. Start from the emitted `codex_goal`, `read_first`, boundaries, and commands.
3. Use the concrete `evidence_run`, `verify`, or `verify_fresh` command rather than inventing an
   evidence path.
4. Route a blocker with `dp goal block --write-artifact` so the next artifact exists in the repo.
5. Recover from repo artifacts with `dp campaign recover --json`.

## Required Pilot Coverage

The pilot test MUST exercise:

1. `dp campaign init` from a non-dp primary spec.
2. `dp campaign refine --write --create-beads` with deterministic Beads command simulation.
3. Generated child specs and ADRs.
4. Generated GoalContracts and EvidencePlans.
5. Campaign lint, loop status, and supervised campaign run.
6. Concrete evidence artifact commands in the handoff.
7. `dp verify --goal` producing a run artifact and a `verified` goal event.
8. `dp goal block --write-artifact` creating a blocker artifact.
9. `dp campaign recover` returning deterministic resume actions before and after verification and
   blocking.
10. Stable JSON and Markdown pilot summaries written in an isolated temp repo.

## Metrics

The pilot summary MUST record:

1. generated goal count;
2. generated evidence plan count;
3. generated child spec count;
4. generated ADR count;
5. Beads issue count requested/created;
6. whether the first handoff was emitted;
7. whether an evidence run artifact was written;
8. whether a verified event was appended;
9. recovery action after verification;
10. recovery action after blocker routing.

These are friction metrics as much as pass/fail metrics. They show how many artifacts a normal
operator needs to inspect and which command advances the campaign.

## Non-Goals

1. No new autonomous runner.
2. No LLM call.
3. No live Beads mutation in the test; Beads calls are simulated deterministically.
4. No claim that the deterministic scaffold semantically completes the product.
5. No product implementation of the Field Report CLI.

## Acceptance

1. The fixture primary spec exists under `tests/fixtures/primary_specs/`.
2. The pilot test runs in an isolated temp repo and writes stable JSON/Markdown summaries.
3. README and runbooks describe the canonical primary-spec-to-first-verified-goal path.
4. The pilot and `make check` pass.
