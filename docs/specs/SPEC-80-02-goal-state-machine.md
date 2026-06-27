# SPEC-80.02 Goal State Machine

Status: active
Issue: dpcx-pb5.3
Parent: SPEC-80

[SPEC-80.02]

## Intent

dp must let Codex operate a goal through explicit state transitions that survive a chat session.
The first state store is append-only JSONL under `.dp/goals/events.jsonl`.

## Requirements

1. `dp goal status <goal.json> --json` MUST reconstruct goal state from the event log.
2. `dp goal claim <goal.json> --agent <name> --lease <duration> --json` MUST validate the goal,
   append a claim event, and record a finite lease.
3. `dp goal start <goal.json> --agent <name> --json` MUST validate the goal and append a start
   event.
4. `dp goal heartbeat <goal.json> --json` MUST append only when a non-stale claim exists.
5. `dp goal block <goal.json> --reason <known-reason> --json` MUST append a structured blocker.
6. `dp goal release <goal.json> --reason <text> --json` MUST append a release event.
7. `dp goal complete <goal.json> --evidence <path> --json` MAY record `evidence_pending`, but
   MUST NOT claim behavioral verification until evidence validation exists.
8. Event output MUST be stable JSON and event replay MUST be sufficient to recover current state.

## Non-Goals

1. No database.
2. No background runner.
3. No fake success state based on Codex narration.
4. No evidence execution.

## Verification

Required evidence for this slice:

```bash
pytest tests/test_goal_state.py
make check
```
