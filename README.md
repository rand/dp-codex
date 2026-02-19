# dp-codex

Codex-native implementation plan for a disciplined, traceable AI-assisted development workflow.

## Purpose

This repository is the execution workspace for building a Codex-first version of the disciplined process capability currently implemented as a Claude plugin.

## Primary Deliverable

A production-ready `dp` toolkit and operating model that provides:

- Spec-first workflow with traceability (`[SPEC-XX.YY]` + `@trace`)
- Task/dependency orchestration over Beads (`bd`) and optional providers
- ADR lifecycle support
- Deterministic enforcement in git hooks and CI
- Decomposition and progress reporting workflows optimized for Codex

## Quick Start

```bash
uv sync --dev
bd ready
./hooks/install.sh
make check
```

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
