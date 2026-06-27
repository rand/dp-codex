# SPEC-80.21 Primary Spec Intake UX and Source Adapters

Status: accepted
Issue: dpcx-pb5.18
Parent: SPEC-80

[SPEC-80.21]

## Intent

`dp campaign init --primary-spec` must be credible for real primary specs supplied by humans, not
only small in-repo examples. A primary spec may be a concise work-back plan, a long system design,
or a remote document imported into the repository. The intake path must make it clear what dp will
write, what it inferred deterministically, what still needs semantic refinement, and what provenance
binds generated artifacts to the source.

Representative inputs include roadmap-style specs such as Waveguide and large system specs such as
Supastructure. dp must not hard-code those projects, but the UX and tests should be strong enough
that those shapes are plausible campaign inputs.

## Command Surface

```bash
dp campaign init --primary-spec <path> --json
dp campaign init --primary-spec <path> --write --json
dp campaign init --primary-spec <url> --json
dp campaign init --primary-spec <url> --write --json
```

URL support may be narrowed to an explicit unsupported-source diagnostic until the provenance and
fetch policy are implemented. A silent or surprising fetch is not acceptable.

## Requirements

1. Dry-run mode MUST preview planned campaign, loop, goal, evidence, and refinement artifacts
   without writing files or creating Beads work.
2. Write mode MUST preserve the existing collision policy: changed artifacts are never overwritten
   silently.
3. Local path intake MUST record stable source provenance: source kind, source path, input hash,
   compiler mode, and creation timestamp where applicable.
4. URL intake MUST either import through an explicit source adapter with provenance or fail with a
   stable unsupported-source diagnostic and exit code `2`.
5. Generated names MUST be stable, readable, and collision-safe for repeated human use.
6. Diagnostics MUST distinguish deterministic extraction from unresolved semantic refinement.
7. Large primary specs MUST produce bounded summaries and structured counts rather than oversized
   JSON blobs.
8. The init report MUST state whether the result is draft, why it is draft, and the exact next dp
   command to refine or promote it.
9. Tests MUST cover dry-run, write mode, local path provenance, unsupported or implemented URL
   behavior, collision handling, and large-spec preview truncation.
10. Docs MUST show adopting-project examples, not dp-codex-only self-reference.

## Formal Invariants

Let `S` be a primary spec input and `P(S)` be the planned artifact set.

1. Dry-run purity: `campaign_init(S, write=false)` writes no files and creates no Beads issues.
2. Source binding: every generated CampaignManifest records `hash(S)` and the source location.
3. Collision safety: if an existing artifact differs from `P(S)`, write mode fails before partial
   mutation.
4. Draft honesty: deterministic intake may create draft work, but it cannot promote a campaign to
   ready.
5. Adapter explicitness: remote inputs are either fetched by a named adapter with provenance or
   rejected with a stable diagnostic.

## Verification

Required evidence:

```bash
pytest tests/test_campaign_init.py tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
