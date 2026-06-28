# Flow Eval Runbook

SPEC-70.05 defines deterministic flow pilots for measuring whether dp's disciplined process works
as an operator experience, not just as isolated commands.

## Purpose

The flow eval answers one practical question:

Can a human or Codex session move from local health to claimed work, implementation artifacts,
verification, preflight hygiene, and task closeout without hidden state or false-positive friction?

## Canonical Automated Eval

Run:

```bash
pytest tests/test_flow_evals.py
```

The test runs in an isolated temp repo and uses fake Beads/preflight probes. It does not mutate the
live tracker and does not call GitHub, a model provider, or the network.
The implementation phase runs a tiny local pytest command and records that actual exit code in the
structured `dp verify` manifest.

The flow exercises:

1. `dp doctor --json`
2. `dp task claim <id> --json`
3. implementation and evidence artifact writes
4. `dp codex preflight --event stop --strict --json`
5. `dp verify --manifest docs/verify/manifest.json --json`
6. `dp task close <id> --reason ... --json`

## Output

The pilot writes stable summaries inside the temp repo:

```text
docs/pilot/SPEC-70.05-guided-task-flow-summary.json
docs/pilot/SPEC-70.05-guided-task-flow-summary.md
```

The JSON summary validates against:

```text
docs/schemas/flow-eval-summary.schema.json
```

## Metrics

Read these metrics as workflow-friction signals, not product-quality claims.

1. `setup_recovery_ok`: `dp doctor` found a usable local workflow state without recovery action.
2. `claim_round_trips`: Beads round trips needed to claim scoped work.
3. `implementation_artifacts_written`: implementation, test, evidence, and manifest artifacts
   written by the pilot.
4. `evidence_levels_verified`: `dp verify` levels that returned `verified`.
5. `evidence_completeness`: verified levels divided by total levels.
6. `strict_preflight_blocking_count`: strict preflight blockers while an active issue and evidence
   signals are present.
7. `false_positive_preflight_blocks`: strict preflight blockers attributable to workflow friction
   rather than missing evidence.
8. `manual_interventions_required`: manual intervention count required by the pilot.
9. `open_blockers`: unresolved blockers at the end of the flow.
10. `closeout_exit_code`: task close command exit code.

## Interpretation

A healthy run has:

1. setup recovery ok;
2. one claim round trip;
3. evidence completeness of `1.0`;
4. zero strict preflight blockers while evidence signals are present;
5. zero manual interventions;
6. zero open blockers;
7. closeout exit code `0`.

If a metric regresses, inspect the step payload in the generated JSON before changing the command
surface. The eval is meant to identify friction, not paper over it.
