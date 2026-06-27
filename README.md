# dp-codex

Disciplined delivery system for Codex: `dp` CLI, policy-driven enforcement, and documentation that turns process into repeatable execution.

## What It Is

`dp-codex` provides a local control plane for any repository that opts into disciplined,
artifact-driven delivery. It is developed in this repository, but its workflow is meant to operate
on the adopting project's own specs, ADRs, Beads tasks, goal contracts, evidence plans, and policy
files.

It provides:

1. A `dp` command surface for traceability, task workflow, ADRs, review, verify, decompose, progress, policy, enforcement, and agent-operable campaigns.
2. Governance controls that run consistently in local hooks and CI.
3. Typed campaign, goal, loop, and evidence-plan contracts that keep Codex work bounded, resumable, and inspectable.
4. End-to-end documentation for users from first-time adopters to maintainers.

## Core Workflows

1. Task lifecycle over Beads (`dp task ...` + `bd`)
2. Spec/trace chain (`[SPEC-XX.YY]` + `@trace SPEC-XX.YY`)
3. ADR-backed architectural decisioning
4. Deterministic review and goal-backward verification
5. Policy-driven pre-commit and pre-push enforcement
6. Decomposition and progress snapshots for fast context recovery
7. Goal contracts, append-only goal state, artifact-producing blockers, and Codex-operable goal prompts
8. Evidence-plan linting and controlled execution for registered, deterministic checks
9. Loop ledgers that select the next ready goal from repo artifacts and goal events
10. Campaign manifests that recover visible campaign state from repo artifacts without chat memory
11. Conservative campaign scaffolding from local primary specs
12. Campaign resume handoffs and event logs for future agent sessions
13. A supervised campaign run step that claims one next goal and emits a Codex-operable handoff
14. Explicit Beads lifecycle synchronization for campaign dependencies and goal state

## Quick Start

```bash
uv sync --dev
dp doctor --json
bd ready --claim --json
./hooks/install.sh
make check
```

In an adopting repository, a goal contract is a project artifact. Validate it and emit a Codex
handoff from that repo's own goal file. If the goal has a linked evidence plan, lint that plan
before relying on it:

```bash
dp goal lint docs/goals/GOAL-my-feature.json --json
dp evidence lint docs/evidence/EVIDENCE-my-feature.json --json
dp evidence run docs/evidence/EVIDENCE-my-feature.json \
  --output docs/evidence-runs/RUN-GOAL-my-feature.json --json
dp verify --goal docs/goals/GOAL-my-feature.json \
  --evidence docs/evidence-runs/RUN-GOAL-my-feature.json --json
dp goal emit docs/goals/GOAL-my-feature.json --format codex --json
```

When a campaign has a loop ledger, ask dp for the next ready goal:

```bash
dp campaign init --primary-spec docs/primary/my-project.md --write --json
dp campaign refine docs/campaigns/CAMPAIGN-my-project.json --write --json
dp campaign lint docs/campaigns/CAMPAIGN-my-project.json --json
dp campaign status docs/campaigns/CAMPAIGN-my-project.json --json
dp campaign recover docs/campaigns/CAMPAIGN-my-project.json --json
dp loop next docs/loops/LOOP-my-campaign.json --claim --emit codex --json
dp campaign run docs/campaigns/CAMPAIGN-my-project.json --driver codex --supervised --json
dp campaign sync-beads docs/campaigns/CAMPAIGN-my-project.json --write --json
```

`dp campaign recover` includes a deterministic `resume` object that tells a future agent whether to
resume an active claim, verify pending evidence, resolve a blocker, claim the next goal, or stop.
`dp campaign sync-beads` is the explicit reconciliation step that keeps Beads dependency and issue
state aligned with the current LoopLedger and dp goal events.

If a claimed goal blocks, route the blocker into the next disciplined artifact instead of leaving it
as chat state:

```bash
dp goal block docs/goals/GOAL-my-feature.json --reason needs_decision --write-artifact --json
```

Run the SPEC-80.19 campaign-control pilot in an isolated temporary repository:

```bash
pytest tests/test_campaign_pilot.py
```

See `docs/runbooks/campaign-pilot.md` for the human and agent flows. The older migration pilot
remains available at `scripts/run_pilot_migration.sh`.

## Reliability Model

1. Deterministic commands with explicit exit semantics.
2. Machine-readable `--json` outputs for automation.
3. Versioned policy in `dp-policy.json`.
4. Auditable bypass path for emergency operations.
5. CI parity with local enforcement behavior.

## Documentation Map

Primary docs index:

- `docs/README.md`

Conceptual model:

- `docs/concepts/disciplined-loop.md`
- `docs/concepts/traceability-chain.md`
- `docs/concepts/governance-and-risk.md`

Role-based guides:

- `docs/guides/quickstart-first-feature.md` (beginner)
- `docs/guides/feature-driver-playbook.md` (intermediate)
- `docs/guides/maintainer-automation-playbook.md` (advanced)

Internals:

- `docs/internals/architecture.md`
- `docs/internals/command-runtime.md`
- `docs/internals/data-contracts.md`
- `docs/internals/testing-strategy.md`

Operational runbooks:

- `docs/runbooks/environment-bootstrap.md`
- `docs/runbooks/developer-commands.md`
- `docs/runbooks/goal-workflow.md`
- `docs/runbooks/enforcement-workflow.md`
- `docs/runbooks/migration-guide.md`
- `docs/runbooks/troubleshooting.md`

Reference and contributor standards:

- `docs/reference/cli-workflow-reference.md`
- `docs/reference/goal-contract-schema.md`
- `docs/reference/goal-state-machine.md`
- `docs/reference/goal-emission.md`
- `docs/reference/evidence-plan-schema.md`
- `docs/reference/loop-ledger-schema.md`
- `docs/reference/campaign-manifest-schema.md`
- `docs/reference/campaign-init.md`
- `docs/reference/campaign-refine.md`
- `docs/reference/campaign-run.md`
- `docs/developer/contributor-handbook.md`
- `docs/developer/documentation-style.md`

## Status

M0-M6 milestone scope has been implemented and empirically validated; v1 readiness is tracked in
`docs/release/v1-readiness.md`.

SPEC-80 campaign-control work has started. The implemented foundation is GoalContract linting,
append-only goal lifecycle state, deterministic blocker artifact routing, Codex prompt emission,
deterministic EvidencePlan linting, controlled EvidencePlan execution, evidence-run verification
into goal state, LoopLedger next-goal scheduling, and campaign resume handoffs with append-only
campaign handoff events. CampaignManifest lint/status/recover is also implemented, so a future
Codex session can inspect repo artifacts and recover visible campaign state without chat memory.
`dp campaign init --primary-spec ... --write --json` can now create a conservative draft campaign
scaffold from a local primary spec, including deterministic semantic-signal extraction for
requirements, evidence, decisions, blockers, and dependency cues. `dp campaign refine ... --write`
can deterministically materialize child spec/ADR stubs, GoalContract and EvidencePlan refinement
metadata, and optionally Beads epics/issues with `--create-beads`. `dp campaign refine --llm`
now emits an agent-mediated request package for the calling agent's model, and
`--llm-response <response.json> --write` imports validated model output as draft refinement
metadata. `dp campaign run <campaign.json> --driver codex --supervised --json` now provides the
first supervised runner slice: it validates campaign state, resolves the current loop, claims one
ready goal, emits the Codex handoff package, and stops without launching Codex, executing evidence,
or marking work verified. If a current-loop goal already has an active non-stale claim, `campaign
run` returns a resume package instead of claiming over it. `dp goal block --write-artifact` now
resolves GoalContract `blocked_routes` into spec, ADR, or EvidencePlan stubs and optional Beads
follow-ups, with routing metadata recorded in the append-only goal event.
`dp campaign sync-beads <campaign.json> --write --json` now reconciles current loop dependencies
and goal lifecycle state back to Beads through explicit `bd dep add`, `bd update`, and `bd close`
operations while leaving dp evidence verification as the source of completion truth.

## Developer Commands

Quality gates are standardized through `make`:

```bash
make test
make lint
make typecheck
make format
make check
```

dp-codex contributors can smoke-test the checked-in goal and evidence fixtures:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
dp goal emit tests/fixtures/goals/valid_spec_70_01.json --format codex --json
dp evidence lint tests/fixtures/evidence/valid_spec_80_05.json --json
dp evidence run tests/fixtures/evidence/valid_run_goal_lint.json --json
dp loop next tests/fixtures/loops/valid_spec_80_04.json --emit codex --json
dp campaign recover tests/fixtures/campaigns/valid_spec_80_06.json --json
dp campaign sync-beads tests/fixtures/campaigns/valid_spec_80_06.json --json
tmpdir="$(mktemp -d)"
cp tests/fixtures/primary_specs/scaffold_full.md "$tmpdir/primary.md"
(cd "$tmpdir" && dp campaign init --primary-spec primary.md --write --json)
(cd "$tmpdir" && dp campaign refine docs/campaigns/CAMPAIGN-primary.json --json)
(cd "$tmpdir" && dp campaign refine docs/campaigns/CAMPAIGN-primary.json --llm --json)
(cd "$tmpdir" && dp campaign run docs/campaigns/CAMPAIGN-primary.json --driver codex --supervised --json)
```
