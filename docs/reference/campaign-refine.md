# Campaign Refine

`dp campaign refine` is an explicit authoring command for draft campaigns.

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --create-beads --json
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

`--llm` is reserved for a future authoring mode. The intended provider is the provider currently
in use by the agent calling dp, usually Codex using a native OpenAI model. LLM refinement may make
network/model calls, but it must record provenance and pass deterministic gates before any output is
treated as ready. LLM judgment is never a blocking gate or verification result.
