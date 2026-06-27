# SPEC-80.14 Deterministic Blocker Artifact Routing

Status: active
Issue: dpcx-pb5.11
Parent: SPEC-80

[SPEC-80.14]

## Intent

SPEC-80's blocker law is that blockers create artifacts. A blocked Codex session should not end in
chat prose that a later session must rediscover. When a valid GoalContract declares a
`blocked_routes` entry and the operator asks dp to write the route, `dp goal block` must create the
next disciplined-process artifact and record enough metadata for recovery.

This slice implements:

```bash
dp goal block <goal.json> --reason <known-reason> --write-artifact --json
```

The command records a blocked event, resolves the route from the GoalContract, writes a
route-specific artifact stub, optionally creates a Beads follow-up, and records all routing results
in the append-only goal event. The command remains deterministic and LLM-free.

## Requirements

1. `dp goal block` MUST continue to validate the GoalContract before appending an event.
2. Known blocker reasons MUST remain explicit and finite.
3. Without `--write-artifact`, current append-only blocked-event behavior MUST remain available.
4. With `--write-artifact`, dp MUST resolve the route from
   `$.blocked_routes.<reason>`.
5. A missing route for a known reason MUST still record the blocked event and MUST return stable
   JSON explaining `missing_blocked_route`.
6. `needs_specification` with `create_spec_stub` MUST write a Markdown spec stub under
   `docs/specs/`.
7. `needs_decision` with `create_adr_stub` MUST write a proposal ADR under `docs/adr/`.
8. `needs_validator` with `create_evidence_stub` MUST write an EvidencePlan JSON stub under
   `docs/evidence/`.
9. Artifact paths MUST be relative, sane, and collision-safe.
10. Reusing an identical existing deterministic artifact is allowed; overwriting a changed
    deterministic artifact is forbidden.
11. If `also_create_beads_issue` is true, dp MUST attempt a Beads follow-up with current
    `bd create ... --json` semantics.
12. Beads failures MUST NOT hide the blocked event or written artifact.
13. All artifact, Beads, and routing metadata MUST be recorded in the blocked event.
14. The command MUST NOT call an LLM.
15. The command MUST NOT execute arbitrary shell from the GoalContract.
16. Emitted Codex and loop handoffs SHOULD include `--write-artifact` in block commands so agents
    use artifact-producing blockers by default.

## Output Shape

Successful routed block:

```json
{
  "ok": true,
  "command": "goal.block",
  "state": "blocked",
  "blocked": {
    "reason": "needs_decision",
    "timestamp": "2026-06-27T00:00:00Z",
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
}
```

Routing failure after event recording:

```json
{
  "ok": false,
  "command": "goal.block",
  "state": "blocked",
  "error": {
    "code": "missing_blocked_route",
    "path": "$.blocked_routes.budget_exhausted",
    "message": "GoalContract does not define a blocker route for budget_exhausted."
  }
}
```

## Formal Invariants

Let `G` be a valid GoalContract, `r` a known blocker reason, and `B(G, r)` the result of
`dp goal block G --reason r --write-artifact`.

1. Event durability:
   if `G` is valid and `r` is known, `B(G, r)` appends exactly one `blocked` event, even when route
   artifact or Beads creation fails.
2. Deterministic route selection:
   the route action is derived only from `G.blocked_routes[r].action`.
3. Gate purity:
   `B(G, r)` performs no LLM calls and no raw-shell execution from generated JSON.
4. Artifact safety:
   deterministic route artifacts are created only under repo-relative `docs/specs/`,
   `docs/adr/`, or `docs/evidence/`; changed existing artifacts are not overwritten.
5. Beads honesty:
   Beads creation success or failure is explicit in JSON and the event log.
6. Recovery:
   `dp goal status G --json` can reconstruct the last blocker reason and routing metadata from
   `.dp/goals/events.jsonl`.

## Non-Goals

1. No automatic unblock or ready-state transition.
2. No campaign-level event log rollup.
3. No evidence execution.
4. No semantic LLM routing.
5. No direct Beads dependency graph synchronization beyond a single follow-up issue.

## Verification

Required evidence:

```bash
pytest tests/test_goal_block_routing.py tests/test_goal_state.py tests/test_goal_emit.py tests/test_loop_ledger.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
