# Data Contracts

DP-Codex treats machine-readable output as a product surface, not a side effect.

## Contract Sources

1. `/docs/schemas/review-output.schema.json`
2. `/docs/schemas/verify-output.schema.json`
3. `/docs/schemas/policy.schema.json`
4. `/docs/schemas/goal-lint-output.schema.json`
5. `/docs/schemas/evidence-lint-output.schema.json`
6. `/docs/schemas/loop-lint-output.schema.json`

## Contracted Command Families

1. `dp review --json`
2. `dp verify --json`
3. `dp policy validate --json`
4. `dp task ... --json`
5. `dp enforce ... --json`
6. `dp goal lint ... --json`
7. `dp goal status/claim/start/heartbeat/block/release/complete/emit ... --json`
8. `dp agent prompt ... --json`
9. `dp evidence lint ... --json`
10. `dp loop lint/status/next ... --json`

## Stability Expectations

1. Field names should remain stable across patch releases.
2. New fields should be additive when possible.
3. Exit codes remain semantically aligned with documented outcomes.

## Evidence Discipline

When a contract changes:

1. Update schema files first.
2. Update CLI behavior and tests.
3. Update runbooks and reference docs.
4. Re-run quality gates and pilot flow if behavior affects user workflows.
