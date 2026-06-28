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
13. Deterministic campaign readiness promotion from draft authoring artifacts to executable graphs
14. Supervised and managed campaign run steps that claim at most one next goal and emit Codex-operable handoffs with stable stop reasons
15. `dp agent launch` as a goal-level adapter that claims, starts, and emits a handoff package without spawning Codex
16. Explicit Beads lifecycle synchronization for campaign dependencies and goal state
17. CLI-first Codex packaging with repo instructions and an optional repo-local campaign-control skill
18. Agent Experience commands for compact bootstrap, capabilities, hints, instruction governance, adoption planning, skills, hooks, and evals

## Quick Start

```bash
uv sync --dev
dp doctor --json
dp task claim --json
dp codex preflight --event stop --json
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
dp campaign init --primary-spec docs/primary/my-project.md --json
dp campaign init --primary-spec docs/primary/my-project.md --write --json
dp campaign refine docs/campaigns/CAMPAIGN-my-project.json --write --create-beads --json
dp campaign ready docs/campaigns/CAMPAIGN-my-project.json --json
# Resolve any reported spec, ADR, evidence, Beads-link, or dependency findings.
dp campaign ready docs/campaigns/CAMPAIGN-my-project.json --write --json
dp campaign lint docs/campaigns/CAMPAIGN-my-project.json --json
dp campaign status docs/campaigns/CAMPAIGN-my-project.json --json
dp campaign recover docs/campaigns/CAMPAIGN-my-project.json --json
dp loop next docs/loops/LOOP-my-campaign.json --claim --emit codex --json
dp campaign run docs/campaigns/CAMPAIGN-my-project.json --driver codex --supervised --json
dp campaign run docs/campaigns/CAMPAIGN-my-project.json --driver codex --supervised --managed --json
dp agent launch --goal docs/goals/GOAL-my-feature.json --driver codex --supervised --json
dp campaign sync-beads docs/campaigns/CAMPAIGN-my-project.json --write --json
```

The first `campaign init` command is a dry-run preview: it plans and lints draft campaign artifacts
without writing them. `--write` creates the same draft artifacts once the preview looks right.

`dp campaign recover` includes a deterministic `resume` object that tells a future agent whether to
resume an active claim, verify pending evidence, resolve a blocker, claim the next goal, or stop.
`dp campaign sync-beads` is the explicit reconciliation step that keeps Beads dependency and issue
state aligned with the current LoopLedger and dp goal events.

If a claimed goal blocks, route the blocker into the next disciplined artifact instead of leaving it
as chat state:

```bash
dp goal block docs/goals/GOAL-my-feature.json --reason needs_decision --write-artifact --json
```

For agent-oriented session startup and command discovery:

```bash
dp agent bootstrap --json --detail brief
dp agent capabilities --json
dp explain DP-HINT-EVIDENCE-MISSING --json
dp instructions audit --json
dp adopt inspect --json
dp hooks audit --json
dp skills audit --json
```

Run the SPEC-80.19 campaign-control pilot in an isolated temporary repository:

```bash
pytest tests/test_campaign_pilot.py
pytest tests/test_flow_evals.py
```

See `docs/runbooks/campaign-pilot.md` for the human and agent campaign-control flows, and
`docs/runbooks/flow-evals.md` for the SPEC-70.05 doctor/claim/verify/preflight/closeout friction
eval. The older migration pilot remains available at `scripts/run_pilot_migration.sh`.

For Codex packaging guidance, see `docs/runbooks/codex-packaging.md` and
`docs/adr/ADR-0014-codex-packaging-stays-cli-first.md`. The current recommendation is deliberately
CLI-first: use `dp`, repository `AGENTS.md`, and the repo-local
`.agents/skills/dp-campaign-control` skill before considering MCP or plugin distribution.

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
- `docs/runbooks/codex-packaging.md`
- `docs/runbooks/agent-session-bootstrap.md`
- `docs/runbooks/agent-session-handoff.md`
- `docs/runbooks/adopting-dp-in-existing-project.md`
- `docs/runbooks/debugging-agent-handoffs.md`
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
- `docs/reference/campaign-ready.md`
- `docs/reference/campaign-run.md`
- `docs/reference/campaign-beads-sync.md`
- `docs/reference/codex-preflight.md`
- `docs/reference/agent-launch.md`
- `docs/reference/agent-response-contract.md`
- `docs/reference/agent-bootstrap.md`
- `docs/reference/agent-capabilities.md`
- `docs/reference/toolcards.md`
- `docs/reference/hint-codes.md`
- `docs/reference/instruction-governance.md`
- `docs/reference/adoption-workflow.md`
- `docs/reference/skills.md`
- `docs/reference/hook-governance.md`
- `docs/reference/agent-usability-evals.md`
- `docs/reference/e2e-flow-matrix.md`
- `docs/developer/contributor-handbook.md`
- `docs/developer/documentation-style.md`

## Status

M0-M7 disciplined delivery, Beads intake, enforcement, flow evals, and Codex integration are
implemented as deterministic CLI workflows.

SPEC-80 campaign-control is implemented as a CLI-first control plane for GoalContracts,
EvidencePlans, LoopLedgers, CampaignManifests, supervised handoffs, recovery, readiness promotion,
blocker artifact routing, and explicit Beads synchronization. It does not spawn Codex or mark work
complete from agent narration.

SPEC-81 agent-experience is implemented for compact response envelopes, ToolCards, stable hints,
bootstrap/capabilities, instruction governance, conservative adoption, focused skills, hook
governance, token budgets, and deterministic usability evals.

SPEC-82.01 records the whole-system release-readiness contract: the public CLI command surface must
stay documented, package-version claims must be explicit, outside-repository smoke checks must run,
deferred MCP/plugin/background-autonomy surfaces must not be overclaimed, and final gates must pass
before publication.

Current release-readiness status and historical v1 evidence live in `docs/release/v1-readiness.md`.

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
agent_tmp="$(mktemp -d)"
cp tests/fixtures/goals/valid_spec_70_01.json "$agent_tmp/goal.json"
(cd "$agent_tmp" && dp agent launch --goal goal.json --driver codex --supervised --json)
pytest tests/test_campaign_run.py tests/test_campaign_managed_run.py tests/test_agent_launch.py
pytest tests/test_flow_evals.py
```
