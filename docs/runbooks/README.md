# Runbooks

Runbooks are operational, step-by-step documents for repeatable execution.

## Core Runbooks

1. `environment-bootstrap.md`: local setup and first-run checks
2. `developer-commands.md`: daily command sequence and quality gates
3. `policy-workflow.md`: policy configuration and validation
4. `enforcement-workflow.md`: hook/CI enforcement and bypass protocol
5. `troubleshooting.md`: failure diagnosis and recovery
6. `codex-integration.md`: opt-in Codex guidance, hooks, and cheap preflight checks
7. `flow-evals.md`: deterministic flow pilots and friction metrics
8. `codex-packaging.md`: CLI-first Codex packaging, repo-local skill, and deferred MCP/plugin rules
9. `agent-session-bootstrap.md`: first-command agent orientation and compact discovery
10. `agent-session-handoff.md`: clean evidence-backed agent closeout
11. `adopting-dp-in-existing-project.md`: inspect-plan-apply-verify adoption flow
12. `debugging-agent-handoffs.md`: hint-led repair for failed handoffs and evidence

## Workflow-Specific Runbooks

1. `adr-workflow.md`
2. `decompose-workflow.md`
3. `progress-workflow.md`
4. `review-workflow.md`
5. `verify-workflow.md`
6. `goal-workflow.md`
7. `task-normalization.md`
8. `task-json-output.md`
9. `output-schemas.md`
10. `migration-guide.md`
11. `campaign-pilot.md`

Runbooks are meant to be executable. If a step cannot be executed as written, update the runbook and the implementation in the same change.
