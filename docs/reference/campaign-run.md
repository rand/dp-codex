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
6. claims at most one ready goal;
7. emits the Codex handoff package and lifecycle commands;
8. stops.

It does not launch Codex, run evidence, verify a goal, infer completion, or loop in the
background.

Successful output has command `campaign.run`, mode `supervised_once`, `autonomous: false`, and
`launched: false`. The `next` object is the `loop.next` package containing the goal id, read-first
paths, evidence plan, allowed paths, lease, Codex `/goal` text, and `dp goal ...` lifecycle
commands.

Exit codes:

1. `0`: one supervised handoff was prepared.
2. `1`: a loaded campaign or loop is invalid, or no ready goal could be prepared.
3. `2`: missing `--supervised`, unsupported driver, malformed input, missing file, or incomplete
   command input.

The JSON contract is documented in `/docs/schemas/campaign-run-output.schema.json`.
