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
7. Goal contracts, append-only goal state, and Codex-operable goal prompts
8. Evidence-plan linting for registered, deterministic checks
9. Loop ledgers that select the next ready goal from repo artifacts and goal events
10. Campaign manifests that recover visible campaign state from repo artifacts without chat memory
11. Conservative campaign scaffolding from local primary specs

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
dp goal emit docs/goals/GOAL-my-feature.json --format codex --json
```

When a campaign has a loop ledger, ask dp for the next ready goal:

```bash
dp campaign init --primary-spec docs/primary/my-project.md --write --json
dp campaign lint docs/campaigns/CAMPAIGN-my-project.json --json
dp campaign status docs/campaigns/CAMPAIGN-my-project.json --json
dp campaign recover docs/campaigns/CAMPAIGN-my-project.json --json
dp loop next docs/loops/LOOP-my-campaign.json --claim --emit codex --json
```

Run an empirical end-to-end pilot in an isolated temporary repository:

```bash
scripts/run_pilot_migration.sh
```

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
- `docs/developer/contributor-handbook.md`
- `docs/developer/documentation-style.md`

## Status

M0-M6 milestone scope has been implemented and empirically validated; v1 readiness is tracked in
`docs/release/v1-readiness.md`.

SPEC-80 campaign-control work has started. The implemented foundation is GoalContract linting,
append-only goal lifecycle state, Codex prompt emission, deterministic EvidencePlan linting, and
LoopLedger next-goal scheduling. CampaignManifest lint/status/recover is also implemented, so a
future Codex session can inspect repo artifacts and recover visible campaign state without chat
memory. `dp campaign init --primary-spec ... --write --json` can now create a conservative draft
campaign scaffold from a local primary spec. Evidence execution, semantic primary-spec compilation,
LLM-assisted refinement, and supervised campaign running remain tracked follow-up work, not current
features.

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
dp loop next tests/fixtures/loops/valid_spec_80_04.json --emit codex --json
dp campaign recover tests/fixtures/campaigns/valid_spec_80_06.json --json
tmpdir="$(mktemp -d)"
cp tests/fixtures/primary_specs/scaffold_full.md "$tmpdir/primary.md"
(cd "$tmpdir" && dp campaign init --primary-spec primary.md --write --json)
```
