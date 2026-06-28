# Release Readiness

Date: 2026-06-28
Decision: Post-SPEC-81 release hardening is in progress.
Current package version: `0.1.0`

## Current Implemented Surface

1. M0-M7 disciplined delivery, Beads intake, enforcement, flow evals, and Codex integration are
   implemented as deterministic CLI workflows.
2. SPEC-80 campaign-control is implemented as a CLI-first control plane for GoalContracts,
   EvidencePlans, LoopLedgers, CampaignManifests, supervised handoffs, recovery, and explicit
   Beads synchronization.
3. SPEC-81 agent-experience is implemented for compact response envelopes, ToolCards, stable
   hints, bootstrap/capabilities, instruction governance, conservative adoption, focused skills,
   hook governance, token budgets, and deterministic usability evals.
4. SPEC-82.01 whole-system release readiness keeps the command reference, version claims,
   outside-repository smoke checks, and final gates aligned with the implemented surface.

## Deferred Surfaces

1. MCP remains deferred until an ADR proves the CLI JSON protocol is materially insufficient.
2. Codex plugin packaging remains deferred until there is a concrete distribution need beyond the
   CLI, repo `AGENTS.md`, and repo-scoped skills.
3. Direct background autonomous agent execution remains out of scope; dp emits bounded handoffs and
   verifies deterministic evidence.
4. Hosted services, dashboards, and cloud dependencies remain out of scope for the current release
   track.

## Outside-Repository Smoke

Run these commands outside the dp-codex repository to prove the installed or editable package works
without accidentally importing from the checkout:

```bash
dp --help
dp doctor --json
dp agent bootstrap --json --detail brief
dp agent capabilities --json
```

In a directory that has not opted into dp-codex, `dp doctor --json` should return a structured
nonzero diagnostic instead of crashing. For a positive health smoke, run `dp doctor --json` from a
safe dp-aware repository outside the dp-codex checkout.

For an editable local install smoke, run from a temporary directory:

```bash
UV_CACHE_DIR=/Users/rand/src/dp-codex/.uv-cache \
  uv run --no-project --with-editable /Users/rand/src/dp-codex dp --help
```

## Final Gate

Do not publish or describe a release as complete until all commands pass in the release candidate:

```bash
make check
dp review --json
dp verify --json
dp doctor --json
bd --readonly status --json
```

## Historical v1.0 Scope Lock

The 2026-02-19 v1.0 scope lock covered M0-M6 and remains archived as historical evidence:

1. Full disciplined loop demonstrable in a clean repository: PASS
   Evidence: `docs/evidence/2026-02-19/pilot-migration.txt`
2. Migration guidance validated by pilot execution: PASS
   Evidence: `docs/pilot/pilot-migration-report.md`, `docs/runbooks/migration-guide.md`
3. No open high-severity core defects: PASS
   Evidence: `docs/pilot/friction-triage.md`
4. Core quality gates pass deterministically: PASS
   Evidence: `docs/evidence/2026-02-19/quality-gates.txt`
5. Local/CI enforcement parity implemented: PASS
   Evidence: `.github/workflows/ci.yml`, `docs/runbooks/enforcement-workflow.md`
6. Bypass protocol and audit conventions documented: PASS
   Evidence: `docs/runbooks/enforcement-workflow.md`, `docs/runbooks/policy-workflow.md`
7. Property-based testing included in verification suite: PASS
   Evidence: `tests/property/test_policy_properties.py`
