# Campaign Init

`dp campaign init` creates a deterministic draft campaign scaffold from a local primary spec.

```bash
dp campaign init --primary-spec docs/primary/example.md --write --json
```

This is a scaffold, not semantic campaign planning. It hashes the primary spec, extracts Markdown
headings, writes lintable draft artifacts, and records `needs_refinement` markers for later
authoring work.

Generated paths:

1. `docs/campaigns/CAMPAIGN-<slug>.json`
2. `docs/campaigns/CAMPAIGN-<slug>.needs_refinement.json`
3. `docs/loops/LOOP-<slug>.json`
4. `docs/goals/GOAL-<slug>-NNN.json`
5. `docs/evidence/EVIDENCE-<slug>-NNN.json`

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
6. `needs_refinement` is expected; it records missing semantic decomposition, validator gaps, and
   decision markers.
