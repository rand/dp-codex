# Testing Strategy

The test strategy mirrors the execution plan: prove behavior with fast local checks and at least one realistic end-to-end flow.

## Test Layers

1. Unit tests (`/tests/unit/`): parsing, validation, normalization, exit behavior.
2. Integration tests (`/tests/integration/`): multi-command scenarios and provider orchestration.
3. Pilot/e2e evidence (`/scripts/run_pilot_migration.sh` + `/docs/evidence/`): realistic, command-driven full loop.
4. Property tests (`/tests/property/`): invariant checks under broader input combinations.

## Current Property-Based Coverage

1. Policy mode/override merge invariants.
2. Unknown policy override rejection invariants.

## Quality Gates

1. `make lint`
2. `make typecheck`
3. `make test`
4. `make check`

## When Adding A New Command

1. Add happy-path and failure-path unit tests.
2. Add JSON-output tests if command supports `--json`.
3. Add integration coverage if command composes with other workflows.
4. Update docs and runbooks in the same change.

If a command changes user behavior without tests, that is not innovation. That is suspense.
