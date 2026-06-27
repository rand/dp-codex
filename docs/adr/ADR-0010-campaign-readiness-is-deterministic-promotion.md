# ADR-0010: Campaign Readiness Is Deterministic Promotion

Status: accepted
Date: 2026-06-27
Spec: [SPEC-80.16](../specs/SPEC-80-16-semantic-campaign-graph-readiness.md)

## Context

Campaign authoring now has multiple sources: deterministic primary-spec scaffold extraction,
deterministic refinement, human edits, Beads materialization, and agent-mediated LLM response
imports. These sources can produce useful draft artifacts, but none of them should be able to mark
a campaign executable by assertion.

If readiness is implicit in `campaign init`, `campaign refine`, or `campaign refine --llm-response`,
then authoring and gating collapse into one step. That would allow heading-derived placeholders,
unreviewed model suggestions, unresolved decisions, or missing validators to leak into the agent
execution loop.

## Decision

Campaign readiness is an explicit deterministic promotion command:

```bash
dp campaign ready <campaign.json> --json
dp campaign ready <campaign.json> --write --json
```

The command reads already-authored artifacts, validates graph closure and refinement resolution,
and promotes `state.status` to `ready` only when deterministic gates pass. It does not call an LLM,
execute evidence, mutate Beads, or infer completion.

## Consequences

1. Authoring commands remain free to draft and refine without becoming blocking gates.
2. Agents get a clear boundary: a campaign is executable only after `campaign ready` passes.
3. LLM output can influence objectives and dependency hints, but readiness requires materialized
   loop edges, validators, specs, and issue links.
4. Failed readiness becomes actionable structured output instead of a vague instruction to review
   the campaign.
5. Future managed runners can refuse non-ready campaigns without reimplementing graph checks.

## Rejected Alternatives

1. **Mark campaigns ready from `campaign refine --write`.** Rejected because deterministic refine
   still creates draft stubs and may preserve `needs_*` states.
2. **Let `campaign refine --llm-response` decide readiness.** Rejected because model-authored
   metadata is not a blocking gate.
3. **Treat `campaign lint` as readiness.** Rejected because schema validity does not prove an
   executable graph has validators, child specs, Beads links, and resolved dependency metadata.
