# Goal State Machine

Goal lifecycle state is reconstructed from append-only events in:

```text
.dp/goals/events.jsonl
```

Current commands:

```bash
dp goal status <goal.json> --json
dp goal claim <goal.json> --agent codex --lease 2h --json
dp goal start <goal.json> --agent codex --json
dp goal heartbeat <goal.json> --json
dp goal block <goal.json> --reason needs_decision --json
dp goal release <goal.json> --reason "context reset" --json
dp goal complete <goal.json> --evidence <run.json> --json
```

Initial state is `ready` when `dp goal lint` passes and no events exist.

Implemented event states:

1. `claimed`: finite lease exists.
2. `started`: claimed or unclaimed agent work has started.
3. `pursuing`: heartbeat recorded for an active non-stale claim.
4. `blocked`: structured blocker recorded.
5. `released`: claim released, or a claim lease is stale.
6. `evidence_pending`: evidence path recorded, but behavioral verification is not implemented.
7. `verified`: recognized from append-only events for loop dependency unlocks; no current `dp goal`
   command writes this state.

Rules:

1. Every mutating command validates the GoalContract first.
2. Claims require finite leases such as `30m`, `2h`, or `1d`.
3. A non-stale claim by one agent blocks another agent from claiming.
4. Heartbeat requires an active non-stale claim.
5. Block reasons are limited to known route types.
6. `complete` records evidence pending; it does not mark verified success.
7. Loop dependencies unlock on verified state, not agent narration or evidence-pending state.
