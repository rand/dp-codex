# Runbooks

Runbooks are operational, step-by-step documents for repeatable execution.

## Core Runbooks

1. `environment-bootstrap.md`: local setup and first-run checks
2. `developer-commands.md`: daily command sequence and quality gates
3. `policy-workflow.md`: policy configuration and validation
4. `enforcement-workflow.md`: hook/CI enforcement and bypass protocol
5. `troubleshooting.md`: failure diagnosis and recovery

## Workflow-Specific Runbooks

1. `adr-workflow.md`
2. `decompose-workflow.md`
3. `progress-workflow.md`
4. `review-workflow.md`
5. `verify-workflow.md`
6. `task-normalization.md`
7. `task-json-output.md`
8. `output-schemas.md`
9. `migration-guide.md`

Runbooks are meant to be executable. If a step cannot be executed as written, update the runbook and the implementation in the same change.
