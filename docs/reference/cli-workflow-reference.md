# CLI Workflow Reference

Quick command reference by workflow.

## Traceability

1. `dp trace coverage [--json] [--spec-glob ...] [--trace-glob ...]`
2. `dp trace validate [--json] [--spec-glob ...] [--trace-glob ...]`

## Task Provider (Beads)

1. `dp task ready [--json]`
2. `dp task show <id> [--json]`
3. `dp task update <id> [--status ...] [--priority ...] [--owner ...] [--json]`
4. `dp task discover <source-id> <title> [flags] [--json]`
5. `dp task close <id> --reason "..." [--json]`

## ADR

1. `dp adr create <title> [--status proposal|accepted|superseded|deprecated] [--json]`
2. `dp adr list [--json]`
3. `dp adr show <id-or-path> [--json]`
4. `dp adr update <id-or-path> --status <status> [--superseded-by ADR-XXXX] [--json]`

## Planning And Progress

1. `dp decompose --item "..." [--preset codex-small|codex-medium|codex-large] [--json]`
2. `dp progress [--output-dir ...] [--watch] [--previous ...] [--json]`

## Review And Verification

1. `dp review [--json]`
2. `dp verify [--manifest ...] [--json]`

## Policy And Enforcement

1. `dp policy validate [--config dp-policy.json] [--json]`
2. `dp enforce pre-commit [--policy dp-policy.json] [--json]`
3. `dp enforce pre-push [--policy dp-policy.json] [--json]`

## Exit Codes (General)

1. `0`: successful/passing outcome
2. `1`: blocking failure
3. `2`: validation/incomplete/usage-path failure (command-specific)
4. `127`: dependency or provider command unavailable

For command-specific details, run `dp <command> --help`.
