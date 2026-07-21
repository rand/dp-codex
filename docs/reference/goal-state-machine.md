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
dp goal outcome <goal.json> --class useful|mixed|not_useful --ref <governed-ref> --json
dp goal ratify <goal.json> --json
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

The `outcome_contact` event is orthogonal to lifecycle state: it does not change the state, it
records real-world contact. Each event carries the outcome class, the governed ref, and
`goal_sha256`, the goal file digest at recording time:

1. `dp goal outcome` deliberately requires no active claim; the owner records contact without
   a lease.
2. `dp goal verify` reports `outcome_confirmed` separately from `verified`. Confirmation is
   latest-wins, consistent with `last_outcome`: true iff the most recent `outcome_contact`
   whose `goal_sha256` matches the current goal digest has class `useful` or `mixed`. A later
   `not_useful` on the unchanged goal retracts an earlier confirmation. Outcome authority is
   scoped: outcomes settle value claims and can revoke done-as-verified; a useful outcome
   never blesses failing verification.
3. Editing the goal file expires confirmation; contact confirms only the content it was
   recorded against.
4. `receipts_since_last_outcome_contact` counts only `verified` events — one receipt per
   verify cycle, `evidence_pending` is not a receipt. It is null before the first contact and
   resets to 0 on each contact.
5. The event log is plain JSONL without signatures; outcome events are auditable, not
   tamper-proof. See `docs/specs/SPEC-83-intent-graph-substrate.md` for trust limits.

The `ratified` event is likewise orthogonal to lifecycle state. `dp goal ratify` applies only
to an unratified agent-proposed root (`intent.parent: null` with `authorship: agent_derived`;
anything else is refused with `not_agent_proposed_root`): it flips `intent.authorship` to
`owner_ratified` — the only goal-file mutation dp performs — and appends a `ratified` event
carrying `goal_sha256`, the digest of the post-edit goal file.

Rules:

1. Every mutating command validates the GoalContract first, with one deliberate exception:
   `dp goal outcome` requires only that the goal file parses as a JSON object with a
   non-empty `id`, so outcomes stay recordable on historical goals that predate current
   lint levels.
2. Claims require finite leases such as `30m`, `2h`, or `1d`.
3. A non-stale claim by one agent blocks another agent from claiming.
4. `claim` and `start` refuse an agent-proposed root goal (`intent.parent: null` with
   `authorship: agent_derived`) with the `unratified_root_goal` envelope error until the
   owner ratifies it via `dp goal ratify` or sets authorship to `owner` or `owner_ratified`.
   Such goals lint clean and appear in `dp graph audit` as `unratified_root` findings.
5. Heartbeat requires an active non-stale claim.
6. Block reasons are limited to known route types.
7. `block --write-artifact` resolves `blocked_routes.<reason>` and writes the next disciplined
   artifact when the route uses `create_spec_stub`, `create_adr_stub`, or `create_evidence_stub`.
8. A routed blocker can return non-zero when artifact or Beads routing fails, but the blocked event
   remains recorded for recovery.
9. `complete` records evidence pending; it does not mark verified success.
10. `goal verify` appends a `verified` event only when the run output is from `dp evidence run`,
   the run passed, the goal id matches, the evidence plan path matches the GoalContract, and the
   current EvidencePlan sha256 matches the run.
11. `dp verify --goal` orchestrates goal lint, evidence lint, optional evidence execution to a
   concrete artifact path, and the same `goal verify` transition.
12. Loop dependencies unlock on verified state, not agent narration or evidence-pending state.

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
