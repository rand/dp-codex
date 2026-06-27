# SPEC-80.12 Agent-Mediated LLM Refinement

Status: active
Issue: dpcx-pb5.9.3
Parent: SPEC-80

[SPEC-80.12]

## Intent

`dp campaign refine` can deterministically materialize campaign scaffold cues into draft specs,
ADRs, GoalContract refinement metadata, EvidencePlan refinement metadata, and optional Beads work.
The next step is LLM-assisted semantic refinement without violating the campaign control-plane
boundary.

The appropriate model provider for local Codex workflows is the provider already in use by the
calling agent. dp should therefore expose an agent-mediated protocol:

1. dp emits a deterministic LLM request package for the calling agent.
2. The calling agent uses its current provider/model to produce a response artifact.
3. dp imports that explicit response artifact only after deterministic validation.
4. Imported model content remains authoring draft metadata until deterministic gates pass.

This gives Codex a real loop it can operate while keeping hooks, CI, lint, evidence execution, and
verification free of model judgment.

## Commands

```bash
dp campaign refine <campaign.json> --llm --json
dp campaign refine <campaign.json> --llm-response <response.json> --write --json
```

`--llm` without `--llm-response` emits a request package and writes nothing. `--llm-response`
imports an explicit model response artifact and requires `--write`.

## Requirements

1. The request command MUST validate the CampaignManifest before request emission.
2. The request command MUST emit stable JSON and write nothing.
3. The request package MUST include the campaign id, prompt template id, prompt hash, response
   schema path, expected output contract, node inputs, and deterministic input hashes.
4. The request package MUST make clear that the calling agent performs the model/network call.
5. Response import MUST require a response artifact path and `--write`.
6. Response import MUST validate schema version, campaign id, prompt hash, provider provenance,
   known goal ids, duplicate goal ids, path sanity, and proposed evidence command shape.
7. Response import MUST reject raw shell strings or shell control tokens in model-proposed evidence
   commands.
8. Invalid response artifacts MUST fail deterministically and MUST NOT write partial artifacts.
9. Successful import MUST preserve campaign state as `draft`.
10. Successful import MUST record LLM provenance with provider, provider_source, model,
    network_calls, prompt_hash, prompt_template, input hashes, response/output hash, dp version,
    linter version, created_at, and reviewed=false.
11. Successful import MAY write model-drafted rationale, objectives, requirements, evidence cues,
    decisions, dependencies, path suggestions, and non-goals into campaign, goal, and evidence
    refinement metadata.
12. Response import MUST NOT mark a campaign, goal, loop node, or evidence run ready, complete, or
    verified.

## Response Contract

Suggested path:

```text
docs/campaigns/CAMPAIGN-<slug>.llm-response.json
```

Shape:

```json
{
  "schema_version": "0.1",
  "campaign_id": "CAMPAIGN-example",
  "prompt_hash": "sha256:...",
  "provider": "calling_agent",
  "provider_source": "calling_agent",
  "model": "unknown",
  "created_at": "2026-06-27T00:00:00Z",
  "campaign_rationale": "Why this refinement shape is useful.",
  "nodes": [
    {
      "goal_id": "GOAL-example-001",
      "objective": "Concrete refined objective.",
      "rationale": "Reasoning for the refinement.",
      "non_goals": ["Excluded work."],
      "requirements": ["Requirement candidate."],
      "evidence": [
        {
          "kind": "registered_command",
          "argv": ["dp", "goal", "lint", "docs/goals/GOAL-example-001.json", "--json"],
          "rationale": "Why this evidence is relevant."
        }
      ],
      "decisions": ["Decision candidate."],
      "dependencies": ["Dependency cue."],
      "read_first": ["docs/primary/example.md"],
      "allowed_paths": ["docs"]
    }
  ]
}
```

## Formal Invariants

Let `C` be a valid CampaignManifest, `Q(C)` the deterministic request package, and `R` an LLM
response artifact.

1. Request purity:
   `emit_request(C)` writes no files and creates no Beads issues.
2. Prompt binding:
   `import_response(C, R)` is valid only when `R.prompt_hash == Q(C).prompt_hash`.
3. Goal closure:
   every `R.nodes[*].goal_id` must be declared by `C.artifacts.goals`.
4. No shell import:
   no imported evidence command may contain shell control syntax or raw shell strings.
5. Atomic rejection:
   if validation fails, the repo file tree is unchanged by response import.
6. Draft preservation:
   successful response import keeps `C.state.status == "draft"`.
7. Judgment separation:
   `R` may draft authoring metadata, but deterministic gates still decide lint, evidence success,
   goal verification, and campaign readiness.

## Non-Goals

1. No hooks or CI model calls.
2. No direct OpenAI SDK integration in this slice.
3. No autonomous campaign runner.
4. No model-based verification.
5. No arbitrary shell execution from model output.

## Verification

Required evidence:

```bash
pytest tests/test_campaign_refine.py tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
