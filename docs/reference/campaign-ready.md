# Campaign Ready

`dp campaign ready` is the deterministic promotion gate between campaign authoring and campaign
execution.

```bash
dp campaign ready docs/campaigns/CAMPAIGN-example.json --json
dp campaign ready docs/campaigns/CAMPAIGN-example.json --write --json
```

Dry-run mode writes nothing. `--write` promotes `state.status` from `draft` to `ready` only when
all readiness gates pass. A campaign already in `ready` is accepted idempotently.

Readiness is stricter than `campaign lint`. Lint proves the manifest and referenced artifacts are
structurally valid. Readiness proves the graph is executable by an agent:

1. CampaignManifest, LoopLedgers, GoalContracts, and EvidencePlans lint.
2. Loop dependencies are explicit and acyclic.
3. Every loop node declares a GoalContract, EvidencePlan, Beads issue id, and child spec.
4. Node EvidencePlans match node goal ids.
5. GoalContract `evidence.evidence_plan` paths match loop node EvidencePlans.
6. Decision-like nodes have declared ADR coverage.
7. No unresolved `needs_refinement`, `needs_specification`, `needs_decision`,
   `needs_validator`, `draft_placeholder`, or `blocked` metadata remains.
8. LLM dependency hints are materialized as LoopLedger `depends_on` edges before execution.

The command never calls an LLM, executes evidence, mutates Beads, launches an agent, or marks any
goal verified.

Exit codes:

1. `0`: campaign graph is ready.
2. `1`: loaded campaign artifacts are valid JSON but fail deterministic readiness gates.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete command
   input inherited from underlying lint.

The JSON contract is documented in `/docs/schemas/campaign-ready-output.schema.json`.
