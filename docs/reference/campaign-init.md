# Campaign Init

`dp campaign init` creates a deterministic draft campaign scaffold from a local primary spec.

```bash
dp campaign init --primary-spec docs/primary/example.md --json
dp campaign init --primary-spec docs/primary/example.md --write --json
```

Without `--write`, the command is a dry-run preview: it plans artifact paths, lints the generated
drafts in an isolated temporary workspace, and writes nothing to the repository. With `--write`, it
creates the same lintable draft artifacts.

This is a draft compiler, not autonomous semantic planning. It hashes the primary spec, extracts
Markdown sections, records deterministic semantic signals, and records `needs_refinement` markers
for later authoring work.

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
campaign cues. Use `dp campaign ready <campaign.json> --write --json` only after refinement
markers, validator gaps, decision coverage, Beads links, and dependency hints have been resolved.

The JSON output includes `write`, `written`, and `preview` booleans plus `next_commands` for the
normal write/refine/ready sequence. Large primary specs are summarized with `section_count`,
`sections_truncated`, `compiler.node_count`, and `compiler.nodes_truncated` so preview output stays
bounded. Individual compiler signal cues are deterministic excerpts capped at 220 characters; the
primary spec remains the source of truth for full source text.

Remote URL intake is deliberately explicit. Until a source adapter exists, URL input fails with
`unsupported_primary_spec_source` and writes nothing.

Exit codes:

1. `0`: scaffold preview or write succeeded, and deterministic lints passed.
2. `1`: generated drafts were valid command input, but deterministic lint found invalid output.
3. `2`: missing file, unsupported input, unsafe path, unsupported source adapter, or an existing
   artifact would be overwritten in write mode.

Safety rules:

1. The command never calls an LLM.
2. The command never executes evidence checks.
3. The command never creates Beads issues.
4. Existing non-identical artifacts are not overwritten.
5. Dry-run mode writes no repository files.
6. Generated campaign state is `draft`, even when all lint gates pass.
7. Dependency cues are not converted into LoopLedger `depends_on` edges.
8. `needs_refinement` is expected; it records missing semantic decomposition, validator gaps, and
   decision markers.
9. Generated scaffolds are expected to fail `dp campaign ready` until reviewed authoring artifacts
   replace placeholders with executable graph contracts.
