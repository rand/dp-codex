# Campaign Init

`dp campaign init` creates a deterministic draft campaign scaffold from a local primary spec.

```bash
dp campaign init --primary-spec docs/primary/example.md --write --json
```

This is a draft compiler, not autonomous semantic planning. It hashes the primary spec, extracts
Markdown sections, records deterministic semantic signals, writes lintable draft artifacts, and
records `needs_refinement` markers for later authoring work.

The JSON output includes a `compiler` object:

1. `mode`: currently `deterministic_markdown_signals`.
2. `llm`: always `false`.
3. `semantic_planning`: always `false`; prose cues are recorded, not treated as authoritative
   campaign decisions.
4. `ready_for_implementation`: always `false`; generated campaigns remain draft.
5. `summary`: counts for sections, implementation candidates, evidence candidates, decision
   nodes, refinement states, and dependency cues.
6. `nodes`: per-section classification, refinement state, routes, and extracted requirement,
   evidence, decision, blocker, and dependency cues.

Generated paths:

1. `docs/campaigns/CAMPAIGN-<slug>.json`
2. `docs/campaigns/CAMPAIGN-<slug>.needs_refinement.json`
3. `docs/loops/LOOP-<slug>.json`
4. `docs/goals/GOAL-<slug>-NNN.json`
5. `docs/evidence/EVIDENCE-<slug>-NNN.json`

Use `dp campaign refine <campaign.json> --write --json` after scaffold creation to materialize
deterministic child spec/ADR stubs and GoalContract/EvidencePlan refinement metadata from the
campaign cues.

Exit codes:

1. `0`: scaffold was written or already exists identically, and deterministic lints passed.
2. `1`: generated artifacts were written, but deterministic lint found invalid output.
3. `2`: missing file, unsupported input, unsafe path, missing `--write`, or an existing artifact
   would be overwritten.

Safety rules:

1. The command never calls an LLM.
2. The command never executes evidence checks.
3. The command never creates Beads issues.
4. Existing non-identical artifacts are not overwritten.
5. Generated campaign state is `draft`, even when all lint gates pass.
6. Dependency cues are not converted into LoopLedger `depends_on` edges.
7. `needs_refinement` is expected; it records missing semantic decomposition, validator gaps, and
   decision markers.
