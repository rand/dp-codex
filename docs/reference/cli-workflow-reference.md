# CLI Workflow Reference

Quick command reference by workflow.

## Traceability

1. `dp trace coverage [--json] [--spec-glob ...] [--trace-glob ...]`
2. `dp trace validate [--json] [--spec-glob ...] [--trace-glob ...]`

## Task Provider (Beads)

1. `dp task ready [--json]`
2. `dp task claim [id] [--json]`
3. `dp task show <id> [--json]`
4. `dp task update <id> [--status ...] [--priority ...] [--owner ...] [--json]`
5. `dp task discover <source-id> <title> [flags] [--json]`
6. `dp task close <id> --reason "..." [--json]`

## ADR

1. `dp adr create <title> [--status proposal|accepted|superseded|deprecated] [--json]`
2. `dp adr list [--json]`
3. `dp adr show <id-or-path> [--json]`
4. `dp adr update <id-or-path> --status <status> [--superseded-by ADR-XXXX] [--json]`

## Planning And Progress

1. `dp decompose --item "..." [--preset codex-small|codex-medium|codex-large] [--json]`
2. `dp progress [--output-dir ...] [--watch] [--previous ...] [--json]`

## Codex Session Integration

1. `dp codex preflight --event session_start|stop [--strict] [--json]`

## Agent Goals

1. `dp goal lint <goal.json> [--json]`
2. `dp goal status <goal.json> [--json]`
3. `dp goal claim <goal.json> --agent <name> [--lease 2h] [--json]`
4. `dp goal start <goal.json> --agent <name> [--json]`
5. `dp goal heartbeat <goal.json> [--json]`
6. `dp goal block <goal.json> --reason <known-reason> [--write-artifact] [--json]`
7. `dp goal release <goal.json> --reason "..." [--json]`
8. `dp goal complete <goal.json> --evidence <run.json> [--json]`
9. `dp goal verify <goal.json> --evidence <run.json> [--json]`
10. `dp goal emit <goal.json> --format codex [--json]`
11. `dp agent prompt --goal <goal.json> --format codex [--json]`
12. `dp agent launch --goal <goal.json> --driver codex [--agent codex] [--lease 2h] --supervised [--json]`

## Evidence Plans

1. `dp evidence lint <evidence.json> [--json]`
2. `dp evidence run <evidence.json> [--output <run.json>] [--force] [--json]`

## Loop Ledgers

1. `dp loop lint <loop.json> [--json]`
2. `dp loop status <loop.json> [--json]`
3. `dp loop next <loop.json> [--claim] [--agent codex] [--lease 2h] [--emit codex] [--json]`

## Campaign Manifests

1. `dp campaign init --primary-spec <path> [--write] [--json]`
2. `dp campaign refine <campaign.json> [--write] [--create-beads] [--llm] [--llm-response <path>] [--json]`
3. `dp campaign ready <campaign.json> [--write] [--json]`
4. `dp campaign lint <campaign.json> [--json]`
5. `dp campaign status <campaign.json> [--json]`
6. `dp campaign recover <campaign.json> [--json]`
7. `dp campaign run <campaign.json> --driver codex --supervised [--managed] [--max-steps 1] [--agent codex] [--lease 2h] [--json]`
8. `dp campaign sync-beads <campaign.json> [--write] [--json]`

## Review And Verification

1. `dp review [--json]`
2. `dp verify [--manifest ...] [--json]`
3. `dp verify --goal <goal.json> [--evidence <run.json>] [--evidence-output <run.json>] [--force] [--json]`

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
