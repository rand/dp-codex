# DP-Codex Documentation

This is the map. The rest is terrain.

DP-Codex turns disciplined software delivery into a repeatable system: observable inputs, explicit decisions, verifiable outputs, and fewer heroics. The goal is not paperwork. The goal is to make good work easier to repeat.

## Choose Your Path

If you are new to the project:

1. Read `/docs/guides/quickstart-first-feature.md`
2. Read `/docs/runbooks/environment-bootstrap.md`
3. Keep `/docs/EXECUTION-PLAN.md` nearby for milestone context

If you are driving feature delivery:

1. Read `/docs/guides/feature-driver-playbook.md`
2. Use workflow details in `/docs/runbooks/`

If you are operating an agent goal contract:

1. Read `/docs/runbooks/goal-workflow.md`
2. Keep `/docs/reference/goal-contract-schema.md` and `/docs/reference/goal-state-machine.md` nearby
3. Keep `/docs/reference/evidence-plan-schema.md` nearby when the goal cites an evidence plan
4. Keep `/docs/reference/loop-ledger-schema.md` nearby when choosing work from a campaign graph
5. Keep `/docs/reference/campaign-manifest-schema.md` nearby when recovering campaign state
6. Keep `/docs/reference/campaign-init.md` nearby when scaffolding from a primary spec
7. Keep `/docs/reference/campaign-ready.md` nearby when promoting a refined campaign graph
8. Keep `/docs/reference/campaign-run.md` nearby when preparing a supervised Codex handoff
9. Keep `/docs/reference/agent-launch.md` nearby when starting one known GoalContract

If you are maintaining policy, quality gates, or release readiness:

1. Read `/docs/guides/maintainer-automation-playbook.md`
2. Read `/docs/internals/architecture.md`

If you want system design and implementation internals:

1. Read `/docs/concepts/README.md`
2. Read `/docs/internals/README.md`

## Workflow Coverage

| Workflow | Primary Guide | Deep Runbook |
| --- | --- | --- |
| Task lifecycle | `/docs/guides/quickstart-first-feature.md` | `/docs/runbooks/task-normalization.md` |
| Traceability | `/docs/concepts/traceability-chain.md` | `/docs/runbooks/decompose-workflow.md` |
| ADR and decisioning | `/docs/guides/feature-driver-playbook.md` | `/docs/runbooks/adr-workflow.md` |
| Agent goals, evidence plans, loop ledgers, and campaign manifests | `/docs/runbooks/goal-workflow.md` | `/docs/reference/goal-contract-schema.md`, `/docs/reference/goal-state-machine.md`, `/docs/reference/goal-emission.md`, `/docs/reference/evidence-plan-schema.md`, `/docs/reference/loop-ledger-schema.md`, `/docs/reference/campaign-manifest-schema.md`, `/docs/reference/campaign-init.md`, `/docs/reference/campaign-refine.md`, `/docs/reference/campaign-ready.md`, `/docs/reference/campaign-run.md`, `/docs/reference/agent-launch.md` |
| Review and verify | `/docs/guides/feature-driver-playbook.md` | `/docs/runbooks/review-workflow.md`, `/docs/runbooks/verify-workflow.md` |
| Enforcement and policy | `/docs/concepts/governance-and-risk.md` | `/docs/runbooks/enforcement-workflow.md`, `/docs/runbooks/policy-workflow.md` |
| Migration and operations | `/docs/guides/maintainer-automation-playbook.md` | `/docs/runbooks/migration-guide.md`, `/docs/runbooks/troubleshooting.md` |

## Doc Families

1. Concepts: why the system exists and how to think with it (`/docs/concepts/`)
2. Internals: how the code actually works (`/docs/internals/`)
3. Guides: role-based walkthroughs by skill level (`/docs/guides/`)
4. Runbooks: precise operational steps (`/docs/runbooks/README.md`)
5. Reference: command and contract lookups (`/docs/reference/`)
6. Developer standards: contribution and doc-quality norms (`/docs/developer/`)

## Foundational Project Docs

1. `/docs/EXECUTION-PLAN.md`: scope, milestones, and success criteria
2. `/AGENTS.md`: execution protocol for Codex-driven development
3. `/docs/specs/SPEC-80-agent-campaign-control-plane-for-dp-codex.md`: current campaign-control direction and non-goals
4. `/docs/release/v1-readiness.md`: current release decision and evidence links

## Principles

1. Be explicit: hidden assumptions become tomorrow's incident reports.
2. Be empirical: if we have not run it, we have not proven it.
3. Be kind to future readers: they are tired and holding a pager.
4. Keep humor dry and useful: one smile is good, confusion is not.
