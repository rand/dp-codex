# SPEC-80.15 Campaign Events and Resume Handoff

Status: active
Issue: dpcx-pb5.12
Parent: SPEC-80

[SPEC-80.15]

## Intent

SPEC-80 requires campaign state to survive the agent session. Goal events already make individual
GoalContracts recoverable, but a future Codex session still needs a campaign-facing answer:

What should I do next, given the current campaign artifacts and event logs?

This slice adds deterministic campaign resume handoff semantics and the first campaign-level event
log. It does not add a background runner or a new scheduler. It derives recovery from the existing
CampaignManifest, current LoopLedger, append-only goal events, and append-only campaign events.

## Commands In Scope

Existing commands gain resume/event fields:

```bash
dp campaign status <campaign.json> --json
dp campaign recover <campaign.json> --json
dp campaign run <campaign.json> --driver codex --supervised --json
```

New state path:

```text
.dp/campaigns/events.jsonl
```

## Requirements

1. `campaign status` and `campaign recover` MUST remain read-only.
2. `campaign status` and `campaign recover` MUST include a deterministic `resume` object.
3. The `resume` object MUST be derived only from linted campaign artifacts, current-loop state,
   append-only goal events, and append-only campaign events.
4. `campaign run --supervised` MUST not claim a new goal when the current loop already contains an
   active claimed, started, or pursuing goal.
5. When an active goal exists, `campaign run --supervised` SHOULD return a resume package for that
   goal instead of advancing to another node.
6. A stale claim MUST not block future work; stale claims should be visible in `resume.stale_claims`
   and ready work should remain claimable.
7. Blocked nodes MUST produce a `resolve_blocker` resume action, including blocker metadata when
   goal events contain it.
8. Evidence-pending nodes MUST produce a `verify_evidence` resume action with the recorded evidence
   path when available.
9. Ready nodes MUST produce a `claim_next_goal` resume action with the exact supervised run command.
10. Fully verified campaigns MUST produce a `campaign_verified` resume action.
11. No-ready/no-active campaigns MUST produce a `no_ready_work` resume action.
12. Successful supervised claims MUST append a campaign event to `.dp/campaigns/events.jsonl`.
13. Campaign events MUST be JSON objects with stable schema version, timestamp, campaign id, event
    type, loop id, and goal/node identifiers where applicable.
14. `campaign status` and `campaign recover` MUST summarize campaign event count and last event.
15. None of these commands may call an LLM or execute evidence checks.

## Resume Decision Table

For current-loop nodes in ledger order:

| Condition | Resume action | Exit behavior |
| --- | --- | --- |
| Any node is `claimed`, `started`, or `pursuing` | `resume_claimed_goal` | `campaign run` returns that handoff without a new claim |
| Any node is `evidence_pending` | `verify_evidence` | caller should run `dp goal verify` |
| Any node is `blocked` | `resolve_blocker` | caller should resolve the blocker artifact or route |
| Any node is `ready` | `claim_next_goal` | caller may run supervised campaign handoff |
| All nodes are `verified` | `campaign_verified` | no more work |
| Otherwise | `no_ready_work` | wait for dependencies or fix campaign artifacts |

Stale claims are reconstructed as released/ready by the GoalState machine; they appear in
`resume.stale_claims` but do not select `resume_claimed_goal`.

## Output Shape

Example `resume` object for an active goal:

```json
{
  "action": "resume_claimed_goal",
  "reason": "A current-loop goal has an active non-stale claim.",
  "campaign_id": "CAMPAIGN-example",
  "loop_id": "LOOP-example",
  "node_id": "node-001",
  "goal_id": "GOAL-example",
  "goal_path": "docs/goals/GOAL-example.json",
  "lease": {
    "holder": "codex",
    "expires_at": "2099-01-01T00:00:00Z",
    "stale": false
  },
  "commands": {
    "status": "dp goal status docs/goals/GOAL-example.json --json",
    "start": "dp goal start docs/goals/GOAL-example.json --agent codex --json",
    "heartbeat": "dp goal heartbeat docs/goals/GOAL-example.json --json",
    "complete": "dp goal complete docs/goals/GOAL-example.json --evidence <run.json> --json",
    "verify": "dp goal verify docs/goals/GOAL-example.json --evidence <run.json> --json",
    "block": "dp goal block docs/goals/GOAL-example.json --reason <reason> --write-artifact --json",
    "release": "dp goal release docs/goals/GOAL-example.json --reason <reason> --json",
    "campaign_run": "dp campaign run docs/campaigns/CAMPAIGN-example.json --driver codex --supervised --json"
  }
}
```

Example campaign event:

```json
{
  "schema_version": "0.1",
  "event": "handoff_claimed",
  "campaign_id": "CAMPAIGN-example",
  "campaign_path": "docs/campaigns/CAMPAIGN-example.json",
  "timestamp": "2026-06-27T00:00:00Z",
  "loop_id": "LOOP-example",
  "node_id": "node-001",
  "goal_id": "GOAL-example",
  "goal_path": "docs/goals/GOAL-example.json",
  "agent": "codex"
}
```

## Formal Invariants

Let `C` be a valid CampaignManifest, `L` its current loop, `G` the goal event log, and `E` the
campaign event log.

1. Read-only recovery:
   `status(C, G, E)` and `recover(C, G, E)` do not write files.
2. Deterministic resume:
   equal `(C, L, G, E)` inputs produce byte-equivalent `resume` fields modulo JSON object ordering.
3. Active-claim preservation:
   if `resume.action == "resume_claimed_goal"`, `campaign run` does not append a new goal claim
   event.
4. Stale-claim recovery:
   stale claims are never treated as active blockers to new work.
5. Handoff event durability:
   every successful new supervised claim appends exactly one `handoff_claimed` campaign event.
6. Gate purity:
   no resume or event operation calls an LLM, executes evidence, or treats narration as proof.

## Non-Goals

1. No campaign database.
2. No autonomous multi-goal runner.
3. No Beads status synchronization.
4. No evidence artifact generation.
5. No readiness promotion from draft to ready.

## Verification

Required evidence:

```bash
pytest tests/test_campaign_recovery.py tests/test_campaign_manifest.py tests/test_campaign_run.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
