# Output Schema Runbook

JSON output contracts for automation are versioned as JSON Schema files:

1. `docs/schemas/review-output.schema.json`
2. `docs/schemas/verify-output.schema.json`

Validation is enforced by unit tests that execute real `dp review --json` and `dp verify --json` flows and validate payloads against these schemas.
