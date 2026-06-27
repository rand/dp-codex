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
dp goal block <goal.json> --reason needs_decision --write-artifact --json
dp goal release <goal.json> --reason "context reset" --json
dp goal complete <goal.json> --evidence <run.json> --json
dp goal verify <goal.json> --evidence <run.json> --json
dp verify --goal <goal.json> --evidence <run.json> --json
dp verify --goal <goal.json> --evidence-output docs/evidence-runs/RUN-<goal-id>.json --json
```

Initial state is `ready` when `dp goal lint` passes and no events exist.

Implemented event states:

1. `claimed`: finite lease exists.
2. `started`: claimed or unclaimed agent work has started.
3. `pursuing`: heartbeat recorded for an active non-stale claim.
4. `blocked`: structured blocker recorded, optionally with route artifact metadata.
5. `released`: claim released, or a claim lease is stale.
6. `evidence_pending`: evidence path recorded, but not yet verified.
7. `verified`: a matching successful `dp evidence run` artifact has been checked against the
   GoalContract and current EvidencePlan.

Rules:

1. Every mutating command validates the GoalContract first.
2. Claims require finite leases such as `30m`, `2h`, or `1d`.
3. A non-stale claim by one agent blocks another agent from claiming.
4. Heartbeat requires an active non-stale claim.
5. Block reasons are limited to known route types.
6. `block --write-artifact` resolves `blocked_routes.<reason>` and writes the next disciplined
   artifact when the route uses `create_spec_stub`, `create_adr_stub`, or `create_evidence_stub`.
7. A routed blocker can return non-zero when artifact or Beads routing fails, but the blocked event
   remains recorded for recovery.
8. `complete` records evidence pending; it does not mark verified success.
9. `goal verify` appends a `verified` event only when the run output is from `dp evidence run`,
   the run passed, the goal id matches, the evidence plan path matches the GoalContract, and the
   current EvidencePlan sha256 matches the run.
10. `dp verify --goal` orchestrates goal lint, evidence lint, optional evidence execution to a
   concrete artifact path, and the same `goal verify` transition.
11. Loop dependencies unlock on verified state, not agent narration or evidence-pending state.

Routed block events include:

```json
{
  "event": "blocked",
  "reason": "needs_decision",
  "routing": {
    "ok": true,
    "action": "create_adr_stub",
    "artifact": {
      "kind": "adr",
      "path": "docs/adr/ADR-0006-example.md",
      "reused": false
    },
    "beads": {
      "requested": true,
      "ok": true,
      "issue_id": "dpcx-..."
    }
  }
}
```
