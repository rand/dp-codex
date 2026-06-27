# Semantic Signals Product

## Implementation Requirements

- The CLI must compile primary specs into campaign artifacts.
- The generated campaign should remain draft until validators pass.
- Depends on GoalContract lint and EvidencePlan lint being available.

## Evidence And Tests

- Verify with `dp campaign lint docs/campaigns/CAMPAIGN-semantic-signals.json --json`.
- Run `pytest tests/test_campaign_init.py`.
- Acceptance requires deterministic JSON output.

## Open Decisions And Risks

- Decide whether LLM refinement should be a separate authoring command.
- Risk: inferred dependencies could create a misleading execution graph.

## Background

This section explains why campaign recovery matters for future Codex sessions.
