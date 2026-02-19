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

## Planning Docs

- `docs/EXECUTION-PLAN.md`: End-to-end phased execution plan with milestones, acceptance criteria, and risk controls
- `AGENTS.md`: Codex operating instructions for implementing this plan
- `docs/runbooks/developer-commands.md`: Canonical local/CI quality gate commands
- `docs/runbooks/environment-bootstrap.md`: First-time contributor setup and troubleshooting
- `docs/runbooks/task-normalization.md`: Canonical status/priority mapping for `dp task`
- `docs/runbooks/task-json-output.md`: Stable `--json` schema for `dp task` automation
- `docs/runbooks/adr-workflow.md`: ADR file conventions and lifecycle transitions
- `docs/runbooks/review-workflow.md`: Deterministic review checks and commit-readiness flow
- `docs/runbooks/verify-workflow.md`: Goal-backward verify levels, outcomes, and exit codes
- `docs/runbooks/output-schemas.md`: JSON schema contracts for review/verify automation output
- `docs/runbooks/decompose-workflow.md`: Context-window-aware DAG decomposition usage
- `docs/runbooks/progress-workflow.md`: Progress snapshots and watch trigger evaluation
- `docs/runbooks/policy-workflow.md`: Enforcement policy modes and per-check overrides

## Status

M0 foundation work is in progress (repository scaffold and command baseline established).

## Developer Commands

Quality gates are standardized through `make`:

```bash
make test
make lint
make typecheck
make format
make check
```
