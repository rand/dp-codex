# Campaign Beads Sync

`dp campaign sync-beads` reconciles a campaign's LoopLedger and append-only goal events with Beads.
It is explicit by design: dry-run mode plans operations, and write mode applies them.

```bash
dp campaign sync-beads docs/campaigns/CAMPAIGN-example.json --json
dp campaign sync-beads docs/campaigns/CAMPAIGN-example.json --write --json
```

The command:

1. validates the CampaignManifest;
2. resolves `state.current_loop` to a declared LoopLedger;
3. reconstructs goal state from `.dp/goals/events.jsonl`;
4. reads existing Beads dependencies with `bd dep list <issue> --json`;
5. plans missing LoopLedger dependency edges as Beads `blocks` dependencies;
6. links routed blocker follow-up issues back to the blocked source issue;
7. maps active, blocked, released, and verified goal states to Beads update/close operations;
8. applies the plan only when `--write` is present.

Dependency edge mapping:

```bash
bd dep add <dependent-issue> <dependency-issue> --type blocks --json
```

LoopLedger dependencies and routed blocker follow-ups both use this edge shape. For blocker
follow-ups, the blocked source issue depends on the follow-up issue created by the blocked route.

Lifecycle mapping:

1. `claimed`, `started`, `pursuing` -> `bd update <issue> --status in_progress --append-notes ... --json`
2. `blocked` -> `bd update <issue> --status blocked --append-notes ... --json`
3. `released` -> `bd update <issue> --status open --append-notes ... --json`
4. `verified` -> `bd close <issue> --reason ... --json`

The command does not use Beads status as proof. Verified still means dp recorded a deterministic
evidence-backed `verified` goal event.

Successful dry-run output has command `campaign.sync-beads`, `write: false`, an `operations` array,
and a `summary` object:

```json
{
  "ok": true,
  "command": "campaign.sync-beads",
  "campaign_id": "CAMPAIGN-example",
  "loop_id": "LOOP-example",
  "write": false,
  "operations": [],
  "summary": {
    "planned": 0,
    "applied": 0,
    "skipped": 0,
    "failed": 0
  }
}
```

Operation statuses:

1. `planned`: would be applied in write mode.
2. `applied`: applied successfully in write mode.
3. `skipped`: already reflected in Beads.
4. `failed`: Beads command failed or returned invalid JSON.

Exit codes:

1. `0`: sync plan produced or applied without operation failures.
2. `1`: campaign/loop/Beads operation failed after valid command input.
3. `2`: missing file, malformed JSON, unsupported schema, or incomplete command input.

Safety rules:

1. No LLM calls.
2. No evidence execution.
3. No Beads mutation without `--write`.
4. No duplicate dependency edges.
5. Beads failures are reported per operation and do not rewrite dp goal events.

The JSON contract is documented in `/docs/schemas/campaign-sync-beads-output.schema.json`.
