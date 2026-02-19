# Command Runtime And Exit Semantics

This document describes how commands are dispatched and how outcomes are encoded.

## Dispatch Model

1. `dp.cli.main._build_parser` defines command trees.
2. Each subcommand binds a concrete handler via `set_defaults(handler=...)`.
3. Handlers return integer exit codes and write text/json outputs.

## Exit-Code Conventions

1. `0`: command completed successfully.
2. `1`: command completed but produced blocking/failed outcome.
3. `2`: usage, validation, or incomplete-state errors where relevant.
4. `127`: required external command unavailable (notably provider commands).

## Deterministic Output Rules

1. JSON output should be stable and sort keys where practical.
2. Human text output should summarize results and actionable next steps.
3. Error paths should include concrete causes, not generic failure text.

## Provider Boundary

`/dp/providers/beads.py` wraps `bd` execution and normalizes failure classes:

1. `BdUnavailableError`
2. `BeadsNotInitializedError`

The CLI layer translates those into consistent exit codes and user-facing messages.

## Enforcement Runtime

`dp enforce` delegates to `/dp/enforcement/engine.py`.

1. Stage-specific check order (`pre-commit`, `pre-push`).
2. Policy-driven blocking/skip behavior.
3. Bypass handling via environment variables.
4. Audit logging to `.dp/bypass-log.jsonl`.
