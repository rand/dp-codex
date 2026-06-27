# SPEC-80.18: Beads Lifecycle Synchronization for Campaigns

Status: accepted
Parent: [SPEC-80](SPEC-80-agent-campaign-control-plane-for-dp-codex.md)
Issue: dpcx-pb5.15

## Problem

SPEC-80 makes dp the campaign control plane, but Beads must remain the issue and dependency
substrate. Before this slice, dp could materialize Beads epics/issues during campaign refinement and
create Beads follow-ups during blocker routing, but normal campaign operation still had an important
gap: LoopLedger dependency edges and goal lifecycle events did not have an explicit deterministic
way to synchronize back to Beads.

If dp keeps operating goals while Beads remains stale, the campaign becomes a parallel tracker. If
dp silently mutates Beads during every goal command, dry-run recovery and local reasoning become
surprising. The required behavior is an explicit synchronization boundary.

## Design

Add a campaign-level synchronization command:

```bash
dp campaign sync-beads <campaign.json> --json
dp campaign sync-beads <campaign.json> --write --json
```

The command reads:

1. the CampaignManifest,
2. the current LoopLedger,
3. LoopLedger `beads_issue_id` fields,
4. append-only goal events from `.dp/goals/events.jsonl`, and
5. existing Beads dependency records.

It emits a stable plan in dry-run mode and applies that plan only when `--write` is present.

## Formal Invariant

For a lint-valid campaign `C` with current loop `L`, let:

* `N` be the loop nodes that have `beads_issue_id`;
* `E_loop` be the set of LoopLedger dependency edges `(dependent_node, dependency_node)`;
* `B(node)` be the node's Beads issue id;
* `S(goal)` be the reconstructed dp goal state from append-only events.

Then `dp campaign sync-beads C --write --json` must satisfy:

1. For every `(a, b)` in `E_loop` where `B(a)` and `B(b)` exist, Beads contains dependency
   `B(a)` depends on `B(b)`.
2. Existing Beads dependency records are not duplicated.
3. For every blocked node whose routed blocker event created a Beads follow-up `F`, Beads contains
   dependency `B(node)` depends on `F`.
4. For every node with `S(goal) in {claimed, started, pursuing}`, dp proposes or writes a Beads
   `in_progress` update for `B(node)`.
5. For every node with `S(goal) = blocked`, dp proposes or writes a Beads note/status update for
   `B(node)` and preserves blocker reason/routing metadata.
6. For every node with `S(goal) = released`, dp proposes or writes a Beads note/status update that
   returns the issue to open work.
7. For every node with `S(goal) = verified`, dp proposes or writes a Beads close operation with an
   evidence-backed reason.
8. No Beads mutation occurs without `--write`.

The dp goal event log remains the source of truth for goal execution. Beads remains the source of
truth for issue/dependency tracking. Synchronization is an explicit reconciliation step between the
two surfaces.

## Command Output

Successful dry-run output:

```json
{
  "ok": true,
  "command": "campaign.sync-beads",
  "campaign_id": "CAMPAIGN-example",
  "write": false,
  "operations": [
    {
      "kind": "dependency",
      "action": "add",
      "issue_id": "dpcx-child",
      "depends_on_id": "dpcx-parent",
      "status": "planned"
    }
  ],
  "summary": {
    "planned": 1,
    "applied": 0,
    "skipped": 0,
    "failed": 0
  }
}
```

Exit codes:

1. `0`: campaign synced or dry-run plan produced without operation failures.
2. `1`: campaign/loop/Beads operation failed after valid command input.
3. `2`: malformed input, missing file, unsupported options, or unreadable campaign state.

## Beads Operations

### Dependency Edges

Loop dependency:

```json
{
  "id": "implementation",
  "beads_issue_id": "dpcx-impl",
  "depends_on": ["decision"]
}
```

syncs to:

```bash
bd dep add dpcx-impl dpcx-decision --type blocks --json
```

Only missing edges are added. Existing dependency records from `bd dep list <issue> --json` are
treated as already synced.

When a blocked goal event includes a routed Beads follow-up issue, sync also wires the source issue
to depend on the follow-up issue. This keeps blocker work in the Beads graph instead of leaving it
as an unrelated task.

### Lifecycle Status

Goal state maps to Beads as follows:

| dp state | Beads operation |
| --- | --- |
| `claimed`, `started`, `pursuing` | `bd update <issue> --status in_progress --append-notes ... --json` |
| `blocked` | `bd update <issue> --status blocked --append-notes ... --json` |
| `released` | `bd update <issue> --status open --append-notes ... --json` |
| `verified` | `bd close <issue> --reason ... --json` |
| `ready`, `waiting`, `evidence_pending` | no status mutation in this slice |

The notes are deterministic summaries of the dp event, not evidence of completion.

## Safety Rules

1. `sync-beads` never calls an LLM.
2. `sync-beads` never executes evidence.
3. Dry-run is read-mostly; it may read Beads dependency state but must not mutate Beads.
4. Write mode uses current Beads 1.0 commands: `bd dep list`, `bd dep add`, `bd update`, and
   `bd close`.
5. Missing `bd`, missing `.beads`, or command failures are reported as structured JSON.
6. Beads failures do not rewrite dp goal events.
7. The command does not infer completion from Beads status; verified still requires dp evidence.

## Acceptance Criteria

1. `dp campaign sync-beads <campaign.json> --json` returns a deterministic dry-run plan.
2. `--write` applies missing LoopLedger dependency edges without duplicating existing Beads edges.
3. `--write` maps claimed/started/pursuing, blocked, released, and verified goal states to explicit
   Beads updates or closes.
4. Operation failures are stable JSON with exit code `1`; malformed input uses exit code `2`.
5. Tests mock Beads commands for dependency reads/adds, update/close operations, existing-edge
   idempotence, and command failure.
6. Docs, README, output schema, trace coverage, and `make check` pass.
