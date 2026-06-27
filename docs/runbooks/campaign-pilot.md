# Campaign Pilot Runbook

SPEC-80.19 defines the first end-to-end control-plane pilot. It proves that dp can take a primary
spec for a non-dp project through campaign artifacts, supervised handoff, evidence verification,
blocker routing, and recovery.

## Pilot Scenario

Fixture:

```text
tests/fixtures/primary_specs/field_report_cli.md
```

The fixture describes a small `field-report` CLI for normalizing operational reports. It is not a
dp-codex implementation spec; it exists to prove dp can drive a disciplined campaign for another
project.

## Canonical Human Path

```bash
dp campaign init --primary-spec docs/primary/field-report-cli.md --write --json
dp campaign refine docs/campaigns/CAMPAIGN-field-report-cli.json --write --create-beads --json
dp campaign lint docs/campaigns/CAMPAIGN-field-report-cli.json --json
dp campaign ready docs/campaigns/CAMPAIGN-field-report-cli.json --json
# Resolve any readiness findings through reviewed child specs, ADRs, validators, Beads links, and edges.
dp campaign ready docs/campaigns/CAMPAIGN-field-report-cli.json --write --json
dp campaign run docs/campaigns/CAMPAIGN-field-report-cli.json --driver codex --supervised --json
dp campaign run docs/campaigns/CAMPAIGN-field-report-cli.json --driver codex --supervised --managed --json
dp verify --goal docs/goals/GOAL-field-report-cli-001.json --json
dp campaign recover docs/campaigns/CAMPAIGN-field-report-cli.json --json
```

The first `dp verify --goal` writes the default evidence artifact:

```text
docs/evidence-runs/RUN-GOAL-field-report-cli-001.json
```

## Canonical Agent Path

An agent should use the supervised handoff package from `dp campaign run`; `--managed` is the
preferred form when the caller needs a stable `stop_reason`. The package contains:

1. `codex_goal`
2. `read_first`
3. `allowed_paths`
4. `evidence_plan`
5. `commands.evidence_run`
6. `commands.complete`
7. `commands.verify`
8. `commands.verify_fresh`
9. `commands.block`
10. `commands.release`

The agent should not invent the goal, invent an evidence path, or self-report completion. It should
use the emitted commands, then recover with:

```bash
dp campaign recover docs/campaigns/CAMPAIGN-field-report-cli.json --json
```

## Automated Proof

Run the pilot:

```bash
pytest tests/test_campaign_pilot.py
```

The test runs in an isolated temp repo, simulates Beads creation deterministically, writes pilot
summary artifacts under `docs/pilots/` inside that temp repo, and asserts:

1. campaign init/refine artifacts exist;
2. child specs and ADRs are written;
3. Beads epic/task creation is requested and recorded;
4. reviewed readiness metadata can promote the campaign to `ready`;
5. supervised campaign run emits a Codex handoff only after readiness;
6. `dp verify --goal` writes an evidence artifact and appends `verified`;
7. blocker routing writes a disciplined artifact and Beads follow-up;
8. campaign recovery returns deterministic actions.

The pilot is a control-plane proof. It does not claim the deterministic campaign scaffold
semantically implements the Field Report CLI.
