# SPEC-70.05 Flow Pilots and Friction Metrics

Status: active
Issue: dpcx-ea9.4
Parent: M7

[SPEC-70.05]

## Intent

SPEC-80 is only useful if a normal human or Codex session can operate dp's disciplined process with
low enough friction that the control plane gets used. Unit tests prove command behavior, but they do
not show whether the workflow hangs together across setup, task claim, implementation evidence,
verification, preflight hygiene, and task closeout.

This spec defines deterministic flow pilots that measure that experience without depending on live
services or model calls.

## Requirements

1. Flow pilots MUST be deterministic, local, and LLM-free.
2. Flow pilots MUST NOT require live Beads, GitHub, network calls, or external model calls.
3. At least one pilot MUST exercise these command families in one flow:
   1. `dp doctor --json`
   2. `dp task claim <id> --json`
   3. an implementation/artifact-writing step
   4. `dp verify --manifest ... --json`
   5. `dp codex preflight --event stop --strict --json`
   6. `dp task close <id> --reason ... --json`
4. Pilot output MUST include stable JSON metrics.
5. Pilot output SHOULD include a human-readable Markdown summary.
6. Metrics MUST cover setup recovery, claim latency or round trips, evidence completeness,
   false-positive preflight friction, and closeout.
7. The pilot MUST use fake or sandboxed Beads surfaces so tests do not mutate the live tracker.
8. Docs MUST explain how to run the pilot and how to interpret its metrics.
9. `make check` MUST pass.

## Metric Contract

The canonical summary schema is `docs/schemas/flow-eval-summary.schema.json`.

Required metric groups:

1. `steps`: ordered command/phase outcomes.
2. `metrics`: quantitative or boolean measurements from the flow.
3. `friction`: counts for false positives, manual interventions, and blockers.
4. `artifacts`: important proof surfaces written or referenced by the pilot.

Initial metrics:

1. `setup_recovery_ok`: `dp doctor` found a usable workflow state without recovery action.
2. `claim_round_trips`: number of Beads calls required to claim scoped work.
3. `implementation_artifacts_written`: count of implementation/evidence artifacts written by the
   pilot.
4. `evidence_levels_verified`: number of `dp verify` levels that returned `verified`.
5. `evidence_completeness`: ratio of verified levels to total levels.
6. `strict_preflight_blocking_count`: blocking findings from strict Codex preflight while evidence
   signals are present.
7. `closeout_exit_code`: exit code from the task close command.

## Non-Goals

1. Do not benchmark autonomous coding quality.
2. Do not run a live Codex session.
3. Do not mutate live Beads state from the automated pilot.
4. Do not replace command-level unit tests.
5. Do not treat pilot success as proof that every future adopting repository will be frictionless.

## Formal Invariants

1. **Determinism invariant:** the same repo revision and same pilot fixture produce the same summary
   fields, excluding file-system temp roots outside reported relative paths.
2. **No-live-service invariant:** the automated pilot is a pure local test with fake Beads
   interactions and patched preflight probes.
3. **Evidence-completeness invariant:** `evidence_completeness =
   evidence_levels_verified / evidence_levels_total`.
4. **False-positive invariant:** strict preflight MUST NOT block when an active issue exists and
   changed code has tests, docs, or evidence signals.
5. **Closeout invariant:** the flow is incomplete unless task closeout exits `0`.

## Verification

Required evidence:

```bash
pytest tests/test_flow_evals.py
dp trace validate --json
dp trace coverage --json
make check
```
