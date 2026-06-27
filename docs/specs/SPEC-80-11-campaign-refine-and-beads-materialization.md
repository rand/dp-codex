# SPEC-80.11 Campaign Refine And Beads Materialization

Status: active
Issue: dpcx-pb5.9.2
Parent: SPEC-80

[SPEC-80.11]

## Intent

`dp campaign init` can now create a draft campaign and extract deterministic primary-spec signals.
The next control-plane step is an explicit authoring command that refines those draft signals into
repo-native artifacts and, when requested, Beads work.

This slice implements deterministic refinement first. It also defines the provenance contract that
SPEC-80.12 uses for LLM-assisted refinement, where the appropriate provider is the provider
currently in use by the agent calling dp, typically Codex using a native OpenAI model. Network and
model calls are allowed only in that explicit authoring mode.

## Command

```bash
dp campaign refine <campaign.json> --json
dp campaign refine <campaign.json> --write --json
dp campaign refine <campaign.json> --write --create-beads --json
```

Agent-mediated LLM refinement is specified and implemented by SPEC-80.12:

```bash
dp campaign refine <campaign.json> --llm --json
dp campaign refine <campaign.json> --llm-response <response.json> --write --json
```

## Requirements

1. `dp campaign refine` MUST validate the CampaignManifest before refinement.
2. Dry-run mode MUST emit stable JSON and write nothing.
3. `--write` MUST write deterministic child artifacts and update the CampaignManifest.
4. `--create-beads` MUST be explicit and MUST require `--write`.
5. Deterministic refinement MUST NOT call an LLM.
6. Deterministic refinement MUST NOT execute evidence.
7. Deterministic refinement MUST NOT mark a campaign ready or verified.
8. The command MUST preserve campaign state as `draft` unless a later deterministic readiness gate
   is implemented.
9. The command MUST refuse to overwrite existing non-identical generated artifacts.
10. The command SHOULD avoid duplicate Beads references on repeated runs by reusing already
    recorded Beads ids in the CampaignManifest.
11. Beads creation MUST use Beads as the issue substrate; dp must not create a parallel task store.
12. `--llm` MUST be authoring-only. SPEC-80.12 implements it as a request/response protocol where
    dp emits an agent-facing request and imports an explicit response artifact through
    deterministic validation.

## Deterministic Refine Output

For each campaign node, deterministic refinement may create or update:

1. child spec stubs under `docs/specs/`
2. ADR stubs under `docs/adr/` for decision nodes
3. GoalContract refinement metadata
4. EvidencePlan refinement metadata
5. CampaignManifest `artifacts.specs`, `artifacts.adrs`, `artifacts.beads_epics`, and
   `artifacts.beads_issues`
6. a refinement report in JSON output

It may not infer dependency edges from prose. Dependency cues remain cues until a deterministic or
reviewed authoring pass materializes them.

## LLM Provenance Contract

When LLM refinement is implemented, every generated or modified artifact MUST record provenance
with at least:

1. `kind`: `llm`
2. `provider`: the actual provider used, or `calling_agent` when dp delegates to the invoking
   agent provider
3. `provider_source`: `calling_agent`, `environment`, or `explicit_config`
4. `model`: the actual model id when known, otherwise `unknown`
5. `network_calls`: `true`
6. `prompt_hash`: sha256 of the prompt sent to the model
7. `prompt_template`: stable template id/version
8. `input_artifact_hashes`: hashes of campaign, primary spec, goals, loops, evidence plans, and
   refinement marker inputs
9. `output_hash`: sha256 of the model response or normalized generated artifact set
10. `dp_version`: dp version or `unknown`
11. `linter_version`: deterministic contract version
12. `created_at`: UTC timestamp
13. `reviewed`: boolean, initially `false`

The LLM may draft semantic fields, rationale, boundaries, and proposed graph structure. It may not
decide validity, evidence success, readiness, completion, or verification.

## Beads Materialization

When `--create-beads` is provided:

1. dp SHOULD create one campaign epic when the manifest has no recorded Beads epic.
2. dp SHOULD create one task issue per refined goal node when the manifest has no recorded Beads
   issue for that node.
3. Created ids MUST be recorded in the CampaignManifest artifact lists.
4. The JSON output MUST report every attempted Beads write and resulting id.
5. Beads creation failures MUST return a blocking failure and leave repo artifacts in a state that
   can be inspected and repaired.

## Formal Invariants

Let `C` be a valid draft CampaignManifest and `R(C)` a deterministic refine result.

1. Dry-run purity:
   `refine(C, write=false)` writes no files and creates no Beads issues.
2. Draft preservation:
   `R(C).campaign.state.status == "draft"`.
3. No model in deterministic mode:
   `R(C).provenance.kind == "deterministic_refine" => network_calls == false`.
4. Explicit Beads mutation:
   Beads writes occur only when `--create-beads` and `--write` are both present.
5. Artifact closure:
   every spec or ADR path recorded in the manifest exists after successful `--write`.
6. Gate separation:
   refinement can generate artifacts, but only lint/evidence/verification commands can make them
   ready or verified.

## Non-Goals

1. No LLM calls in this deterministic slice.
2. No supervised runner.
3. No evidence execution.
4. No campaign verification inference.
5. No replacement for Beads.

## Verification

Required evidence for this slice:

```bash
pytest tests/test_campaign_refine.py tests/test_campaign_init.py tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
```
