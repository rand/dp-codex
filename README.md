# dp-codex

Disciplined delivery system for Codex: `dp` CLI, policy-driven enforcement, and documentation that turns process into repeatable execution.

## What It Is

`dp-codex` is the project itself, not just a planning artifact. It provides:

1. A production-ready `dp` command surface for traceability, task workflow, ADR, review, verify, decompose, progress, policy, and enforcement.
2. Governance controls that run consistently in local hooks and CI.
3. An operating model that supports real delivery loops, not merely command demos.
4. End-to-end documentation for users from first-time adopters to maintainers.

## Core Workflows

1. Task lifecycle over Beads (`dp task ...` + `bd`)
2. Spec/trace chain (`[SPEC-XX.YY]` + `@trace SPEC-XX.YY`)
3. ADR-backed architectural decisioning
4. Deterministic review and goal-backward verification
5. Policy-driven pre-commit and pre-push enforcement
6. Decomposition and progress snapshots for fast context recovery

## Quick Start

```bash
uv sync --dev
bd ready
./hooks/install.sh
make check
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
- `docs/runbooks/enforcement-workflow.md`
- `docs/runbooks/migration-guide.md`
- `docs/runbooks/troubleshooting.md`

Reference and contributor standards:

- `docs/reference/cli-workflow-reference.md`
- `docs/developer/contributor-handbook.md`
- `docs/developer/documentation-style.md`

## Status

M0-M6 milestone scope has been implemented and empirically validated; v1 readiness is tracked in `docs/release/v1-readiness.md`.

## Developer Commands

Quality gates are standardized through `make`:

```bash
make test
make lint
make typecheck
make format
make check
```
