# DP Codex Execution Plan

## 1. Goal

Build a Codex-native disciplined development toolkit that matches or exceeds the current capability set while removing Claude-specific runtime coupling.

## 2. Success Criteria

The project is successful when all are true:

1. Teams can run the full disciplined loop (Orient -> Specify -> Decide -> Test -> Implement -> Review -> Close) in Codex.
2. Enforcement does not depend on Claude hook events.
3. Core workflows are deterministic and runnable from shell/CI.
4. At least one realistic pilot project can adopt with <= 30 minutes setup.

## 3. Scope

### In Scope

1. `dp` CLI for task/spec/adr/trace/review/verify/decompose/progress workflows.
2. Beads-first task integration; optional adapters as follow-on.
3. Git-hook and CI enforcement layers.
4. Codex-optimized operating docs (`AGENTS.md`, issue templates, command runbooks).
5. Migration guidance from the current plugin workflow.

### Out of Scope (Initial)

1. GUI dashboard.
2. Real-time cloud service dependencies.
3. Multi-tenant hosted backend.

## 4. Product Strategy

### Design Principle

Separate stable process logic from agent-platform integration.

### Layering

1. **Core Engine Layer**: validation, traceability, decomposition, reporting.
2. **Workflow CLI Layer**: user-facing `dp` commands.
3. **Enforcement Layer**: git hooks + CI checks.
4. **Agent Experience Layer**: Codex-oriented instructions and task slicing discipline.

## 5. Target Repository Architecture

```text
.
├── AGENTS.md
├── README.md
├── docs/
│   ├── EXECUTION-PLAN.md
│   ├── specs/
│   ├── adr/
│   └── runbooks/
├── dp/
│   ├── core/
│   ├── cli/
│   ├── providers/
│   └── enforcement/
├── hooks/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── pyproject.toml (or equivalent runtime manifest)
```

## 6. Milestones

## M0: Foundation and Standards

### Outcomes

1. Baseline project skeleton exists.
2. Toolchain and command entrypoints are standardized.
3. Quality gates are runnable locally and in CI.

### Tasks

1. Establish language/runtime and packaging baseline.
2. Define canonical developer commands (`test`, `lint`, `typecheck`, `format`).
3. Add CI pipeline with fast failure on lint/test/type errors.
4. Add runbooks for environment bootstrapping.

### Exit Criteria

1. New contributor can bootstrap and run all quality gates with one documented path.
2. CI reliably executes the same gate set.

## M1: Traceability Core (Spec + Trace)

### Outcomes

1. Spec parser and `@trace` resolution engine is deterministic.
2. Coverage and validation commands produce machine-readable output.

### Tasks

1. Implement spec ID discovery (`[SPEC-XX.YY]`).
2. Implement trace marker discovery (`@trace SPEC-XX.YY`).
3. Build coverage report logic (covered/uncovered specs).
4. Add unresolved reference detection and clear diagnostics.

### Exit Criteria

1. `dp trace coverage` reports total/covered/uncovered specs.
2. `dp trace validate` fails with non-zero code on broken references.
3. Unit tests cover parser and validator edge cases.

## M2: Task Workflow Layer

### Outcomes

1. Unified task command surface exists on top of Beads.
2. Discovery and dependency-aware flow is supported.

### Tasks

1. Implement `dp task ready/show/update/close/discover` wrappers.
2. Normalize status and priority semantics.
3. Add structured output mode (`--json`) for automation.
4. Add robust error handling for missing `bd` or uninitialized `.beads`.

### Exit Criteria

1. Task lifecycle can be completed end-to-end through `dp task` commands.
2. Failure modes are actionable and non-ambiguous.

## M3: ADR + Review + Verify

### Outcomes

1. Architectural decisions are first-class (`dp adr ...`).
2. Review and goal-backward verification are deterministic.

### Tasks

1. Implement ADR creation/list/update validation.
2. Implement checklist-based review command with blocking vs advisory findings.
3. Implement verification levels (truths, artifacts, links).
4. Add JSON output schemas for review/verify consumers.

### Exit Criteria

1. `dp adr` handles lifecycle from proposal to supersession.
2. `dp review` and `dp verify` return stable exit codes and outputs.
3. Integration tests cover at least one complete feature workflow.

## M4: Decompose + Progress (Codex-Optimized)

### Outcomes

1. Spec decomposition supports Codex context-window assumptions.
2. Progress reporting supports agent/human context recovery.

### Tasks

1. Port or reuse decomposition engine and keep `--context-window` configurable.
2. Validate sizing heuristics with Codex baseline presets.
3. Implement progress snapshot and watch-mode triggers.
4. Generate concise agent bootstrap section in reports.

### Exit Criteria

1. `dp decompose` emits executable plans and validated DAGs.
2. `dp progress` generates markdown + JSON snapshots.
3. Fresh Codex session can orient from latest report in <= 2 minutes.

## M5: Enforcement and Governance

### Outcomes

1. Strict/guided/minimal enforcement works via git hooks and CI, not runtime prompt hooks.
2. Policy is configurable per repository.

### Tasks

1. Implement pre-commit checks (tests/traces/required metadata).
2. Implement pre-push checks (sync/status safeguards).
3. Create policy config schema with per-check overrides.
4. Add bypass logging conventions for emergency workflows.

### Exit Criteria

1. Enforcement is reproducible in local dev and CI.
2. Policy changes are auditable and versioned.

## M6: Pilot, Migration, and Hardening

### Outcomes

1. At least one pilot migration completes successfully.
2. Operational docs are good enough for independent adoption.

### Tasks

1. Run a pilot migration from current workflow to `dp-codex`.
2. Capture friction points and patch onboarding gaps.
3. Publish migration checklist and troubleshooting guide.
4. Lock v1.0 scope and create post-1.0 backlog.

### Exit Criteria

1. Pilot team can execute full workflow without maintainer intervention.
2. Known defects are triaged with severity and ownership.

## 7. Codex Optimization Strategy

## Task Sizing Rules

1. Keep implementation issues in the 1-3 hour range.
2. Split when changes touch more than 3 subsystems.
3. Require explicit acceptance checks per issue.

## Issue Template Requirements

Each issue should include:

1. Objective and non-goals.
2. Files expected to change.
3. Verification commands.
4. Failure/rollback notes.

## Context Discipline

1. Provide focused file lists in issue descriptions.
2. Avoid requiring full-repo reads for routine tasks.
3. Maintain `docs/runbooks/` for common workflows to reduce repeated discovery.

## Determinism Requirements

1. All major commands must have `--json` output.
2. Exit codes must map to documented outcomes.
3. Side effects should be explicit and logged.

## 8. Quality and Test Plan

## Test Pyramid

1. Unit tests for parsing, validation, and transformations.
2. Integration tests for CLI-to-provider behavior.
3. End-to-end tests for complete disciplined loop scenarios.

## Minimum Coverage Targets

1. Core parser/validator modules: >= 90% line coverage.
2. CLI orchestration modules: >= 80% line coverage.
3. Provider adapters: happy path + failure path coverage.

## Required Verification Gates

1. Lint.
2. Type check.
3. Unit + integration tests.
4. E2E smoke test for release candidates.

## 9. Risks and Mitigations

1. **Risk**: Tight coupling reintroduced through ad hoc agent prompts.
   **Mitigation**: keep enforcement in CLI/hooks/CI; treat prompt guidance as advisory only.
2. **Risk**: Context-window assumptions drift across models.
   **Mitigation**: keep sizing configurable; collect usage telemetry from pilot repos.
3. **Risk**: Task provider variance causes inconsistent semantics.
   **Mitigation**: canonical internal model + explicit capability matrix.
4. **Risk**: Overly strict enforcement blocks legitimate fast-path fixes.
   **Mitigation**: guided/minimal modes + audited bypass path.

## 10. Initial Backlog Seed (Execution Order)

1. Bootstrap repo structure and command harness.
2. Implement spec/trace parser + validation.
3. Implement coverage reporting.
4. Implement Beads task wrapper surface.
5. Implement ADR lifecycle commands.
6. Implement review and verify modules.
7. Port decompose/progress workflows.
8. Add enforcement hooks and policy schema.
9. Run pilot migration and document gaps.
10. Cut v1.0 release checklist.

## 11. Definition of Done (Per Milestone)

1. All milestone exit criteria met.
2. Tests and CI green.
3. Documentation updated for new/changed commands.
4. Follow-up work captured as explicit issues.

## 12. Release Readiness (v1.0)

1. Full disciplined loop demonstrable in a clean repo.
2. Migration guide validated by at least one external pilot.
3. No open high-severity defects in core workflows.
4. Command/help docs are complete and accurate.
