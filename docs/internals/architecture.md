# Architecture

DP-Codex intentionally separates process logic from integration surfaces.

## Layering

1. Core engine (`/dp/core/`): parsing, validation, review, verify, decomposition, progress, goal lint, goal state, goal emission, evidence lint, loop-ledger scheduling, and campaign manifest recovery.
2. CLI layer (`/dp/cli/main.py`): command parsing, orchestration, output formatting, exit codes.
3. Provider layer (`/dp/providers/`): external systems (currently Beads via `bd`).
4. Enforcement layer (`/dp/enforcement/`): policy-driven checks for hooks and CI.

## Runtime Shape

```text
user/CI command
  -> argparse dispatch (dp.cli.main)
    -> core/provider/enforcement module
      -> structured report (dataclass -> dict/json)
        -> stable exit code
```

## Primary Module Responsibilities

1. `/dp/core/spec_parser.py`: discovers `[SPEC-XX.YY]` declarations.
2. `/dp/core/trace_parser.py`: discovers and validates `@trace` markers.
3. `/dp/core/validation.py`: unresolved and malformed trace diagnostics.
4. `/dp/core/review.py`: deterministic pre-commit readiness checks.
5. `/dp/core/verify.py`: goal-backward verification across truths/artifacts/links.
6. `/dp/core/policy.py`: policy schema loading and mode/override resolution.
7. `/dp/core/goal_lint.py`: deterministic GoalContract validation.
8. `/dp/core/goal_state.py`: append-only goal event replay and lifecycle commands.
9. `/dp/core/goal_emit.py`: Codex prompt emission from valid GoalContracts.
10. `/dp/core/evidence_lint.py`: deterministic EvidencePlan validation for registered checks.
11. `/dp/core/loop_ledger.py`: deterministic LoopLedger lint, status, and next-goal packaging.
12. `/dp/core/campaign_manifest.py`: deterministic CampaignManifest lint, status, and recovery.
13. `/dp/core/events.py`: JSONL event helpers.
14. `/dp/enforcement/engine.py`: executes policy-selected checks and bypass audit logging.

## Design Constraints

1. Determinism over convenience.
2. Explicit side effects.
3. Stable machine-readable output for automation.
4. Minimal hidden state.

When extending architecture, prefer adding a composable core function first and wiring CLI behavior second.
