# Campaign Refine

`dp campaign refine` is an explicit authoring command for draft campaigns.

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --create-beads --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --llm --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --llm-response response.json --write --json
```

Current mode:

1. `deterministic_refine`
2. no LLM calls
3. no evidence execution
4. no campaign verification inference
5. campaign state remains `draft`

Dry-run mode writes nothing and creates no Beads issues. `--write` creates deterministic child spec
stubs, ADR stubs for decision nodes, and GoalContract/EvidencePlan refinement metadata, then
records the paths in the CampaignManifest.

`--create-beads` is explicit and requires `--write`. It creates or reuses a campaign epic and task
issues, then records Beads ids in the manifest. Beads remains the task substrate.

LLM-assisted refinement is agent-mediated. `--llm --json` emits a deterministic request package for
the calling agent's current provider/model and writes nothing. The agent performs the model/network
call and writes a response artifact matching
`docs/schemas/campaign-refine-llm-response.schema.json`.

`--llm-response <response.json> --write --json` imports that response only after deterministic
validation: campaign id, prompt hash, provider provenance, known goal ids, path sanity, and
argv-only evidence proposals without raw shell syntax. Imported model content is recorded as draft
authoring metadata on the campaign, GoalContracts, and EvidencePlans. It never marks work ready,
complete, or verified. LLM judgment is never a blocking gate or verification result.
