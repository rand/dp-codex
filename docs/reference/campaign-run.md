# Campaign Run

`dp campaign run` is a supervised, single-step handoff command for agent-facing campaign
operation.

```bash
dp campaign run docs/campaigns/CAMPAIGN-example.json --driver codex --supervised --json
```

The command:

1. requires `--supervised`;
2. supports only `--driver codex` in this slice;
3. validates and reconstructs CampaignManifest status;
4. resolves `state.current_loop` to a declared LoopLedger;
5. calls the same protocol as `dp loop next --claim --emit codex`;
6. returns an existing active claim as a resume package instead of claiming over it;
7. claims at most one ready goal when no active claim must be resumed;
8. appends a `.dp/campaigns/events.jsonl` `handoff_claimed` event for a new claim;
9. emits the Codex handoff package and lifecycle commands, including `evidence_run`, `complete`,
   `verify`, and `verify_fresh` with concrete evidence artifact paths when available;
10. stops.

It does not launch Codex, run evidence, verify a goal, infer completion, or loop in the
background.

Successful output has command `campaign.run`, mode `supervised_once`, `autonomous: false`, and
`launched: false`. When a new goal is claimed, the `next` object is the `loop.next` package
containing the goal id, read-first paths, evidence plan, allowed paths, lease, Codex `/goal` text,
and lifecycle/evidence commands. When a current-loop goal already has an active non-stale claim,
the `next` object is a `campaign.resume` package with action `resume_claimed_goal`.

New-claim runs also include:

```json
{
  "campaign_event_log": ".dp/campaigns/events.jsonl",
  "campaign_event": {
    "schema_version": "0.1",
    "event": "handoff_claimed",
    "campaign_id": "CAMPAIGN-example",
    "loop_id": "LOOP-example",
    "goal_id": "GOAL-example"
  }
}
```

Exit codes:

1. `0`: one supervised handoff was prepared.
2. `1`: a loaded campaign or loop is invalid, or no ready goal could be prepared.
3. `2`: missing `--supervised`, unsupported driver, malformed input, missing file, or incomplete
   command input.

The JSON contract is documented in `/docs/schemas/campaign-run-output.schema.json`.
