# Output Schema Runbook

JSON output contracts for automation are versioned as JSON Schema files:

1. `docs/schemas/review-output.schema.json`
2. `docs/schemas/verify-output.schema.json`
3. `docs/schemas/policy.schema.json`
4. `docs/schemas/goal-lint-output.schema.json`
5. `docs/schemas/evidence-lint-output.schema.json`
6. `docs/schemas/loop-lint-output.schema.json`
7. `docs/schemas/campaign-lint-output.schema.json`
8. `docs/schemas/campaign-init-output.schema.json`

Validation is enforced by unit tests that execute real JSON-producing flows and validate payloads
against these schemas where a stable schema exists. Other JSON command families are covered by
focused CLI tests until their schemas are promoted into `docs/schemas/`.
