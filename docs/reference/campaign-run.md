# Campaign Run

`dp campaign run` is a supervised, single-step handoff command for agent-facing campaign
operation.

```bash
dp campaign run docs/campaigns/CAMPAIGN-example.json --driver codex --supervised --json
dp campaign run docs/campaigns/CAMPAIGN-example.json --driver codex --supervised --managed --json
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

For generated campaigns, run `dp campaign ready <campaign.json> --write --json` before using
`campaign run` as the execution entrypoint. `campaign run` refuses manifests whose
`state.status` is still `draft` and returns a `campaign_not_ready` error with the exact readiness
promotion command. This keeps draft compiler/refinement markers out of agent handoffs.

Successful one-step output has command `campaign.run`, mode `supervised_once`, `autonomous: false`,
and `launched: false`. When a new goal is claimed, the `next` object is the `loop.next` package
containing the goal id, read-first paths, evidence plan, allowed paths, lease, Codex `/goal` text,
and lifecycle/evidence commands. When a current-loop goal already has an active non-stale claim,
the `next` object is a `campaign.resume` package with action `resume_claimed_goal`.

## Managed Mode

`--managed` wraps the same supervised protocol in a stable stop-reason envelope:

```bash
dp campaign run docs/campaigns/CAMPAIGN-example.json \
  --driver codex --supervised --managed --max-steps 1 --json
```

Managed mode still claims at most one ready goal per invocation. It exists so a human, Codex
session, or future thin adapter can ask dp for the next campaign action and receive a deterministic
answer without interpreting the full status payload itself.

Managed output has mode `managed_supervised`, `autonomous: false`, `launched: false`,
`stop_reason`, `iterations`, `next`, and `stop_conditions`.

Stable stop reasons:

1. `campaign_not_ready`: the manifest is still draft; run `dp campaign ready`.
2. `stale_lease`: a stale claim is present and must be handled explicitly before advancing.
3. `active_claim`: resume the active claimed/started/pursuing goal.
4. `evidence_pending`: verify recorded evidence before claiming more work.
5. `blocked`: resolve the blocker route before dependent work advances.
6. `handoff_claimed`: one ready goal was claimed and emitted for Codex.
7. `campaign_verified`: all current-loop goals are verified.
8. `no_ready_work`: no goal is ready, active, blocked, evidence-pending, or verified.
9. `invalid_max_steps`: the requested managed step bound is outside the supported range.

`--max-steps` is bounded for API stability. In this slice the command still stops after one
observed condition or one handoff, so it is not a background multi-goal runner.

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

1. `0`: a handoff was prepared, an active claim should be resumed, or the current loop is already
   verified.
2. `1`: a loaded campaign or loop is invalid, no ready goal could be prepared, evidence is pending,
   a blocker must be resolved, or a stale lease requires explicit handling.
3. `2`: missing `--supervised`, unsupported driver, invalid `--max-steps`, malformed input,
   missing file, or incomplete command input.

The JSON contract is documented in `/docs/schemas/campaign-run-output.schema.json`.
