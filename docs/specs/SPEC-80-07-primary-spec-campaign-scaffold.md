# SPEC-80.07 Primary Spec Campaign Scaffold

Status: active
Issue: dpcx-pb5.7
Parent: SPEC-80

[SPEC-80.07]

Implementation note, 2026-06-27: SPEC-80.09 extends this scaffold with deterministic
semantic-signal extraction. The guarantees in this document still apply: generated artifacts remain
draft, no LLM is called, no evidence is executed, and dependency edges are not inferred from prose.

## Intent

dp must be able to turn a local primary spec into a recoverable campaign shell before it can
perform semantic campaign compilation. This slice implements a conservative scaffold only: it
hashes the primary spec, extracts Markdown headings mechanically, writes deterministic draft
campaign artifacts, and records `needs_refinement` markers wherever human or LLM authoring would be
needed.

The scaffold is useful only if the artifacts it creates are already compatible with deterministic
gates. It must not pretend to have understood implementation semantics.

## Command

```bash
dp campaign init --primary-spec <path> --write --json
```

Exit codes:

1. `0`: scaffold was written or already exists identically, and deterministic lints passed.
2. `1`: scaffold artifacts were written but deterministic lint found invalid output.
3. `2`: missing file, unsupported input, unsafe path, missing `--write`, or an existing artifact
   would be overwritten.

## Contract

The command MUST:

1. Accept a local, sane relative primary-spec path.
2. Reject URLs, missing files, absolute paths, parent traversal, and other unsafe paths.
3. Compute `sha256:<hex>` for the primary spec.
4. Derive a deterministic slug from the primary spec filename.
5. Identify Markdown ATX headings deterministically.
6. Write a CampaignManifest under `docs/campaigns/`.
7. Write a LoopLedger under `docs/loops/`.
8. Write at least one draft GoalContract under `docs/goals/`.
9. Write EvidencePlan stubs under `docs/evidence/` using registered checks only.
10. Write a `needs_refinement` marker under `docs/campaigns/`.
11. Set the campaign manifest state to `draft`.
12. Run deterministic lint over generated campaign, loop, goals, and evidence plans.
13. Return stable JSON containing generated paths, section extraction results, refinement markers,
    lint summaries, and the primary spec hash.

The command MUST NOT:

1. Call an LLM.
2. Execute evidence checks.
3. Create Beads issues.
4. Infer dependencies between sections.
5. Overwrite existing non-identical artifacts.
6. Treat generated draft goals as proof of campaign readiness.

## Refinement Routing

The scaffold MUST produce machine-readable `needs_refinement` markers. Deterministic initial
routes are:

1. `needs_specification` when the primary spec has no major sections or needs semantic
   decomposition.
2. `needs_validator` when the extracted headings do not mention evidence, tests, validation,
   verification, acceptance, or proof.
3. `needs_decision` when extracted headings mention decisions, open questions, risks, or tradeoffs.

These markers are not failures. They are explicit next artifacts for later authoring commands or
human/Codex work.

## Formal Invariants

Let `P` be a primary spec file and `S(P)` the ordered list of extracted major sections. Let
`G(P)` be the generated GoalContracts, `E(P)` the generated EvidencePlans, `L(P)` the generated
LoopLedger, `M(P)` the generated CampaignManifest, and `R(P)` the refinement marker.

1. Determinism: for unchanged `P`, `scaffold(P)` produces byte-identical JSON artifacts.
2. Closure: every `L(P).nodes[*].goal_path` is in `M(P).artifacts.goals`.
3. Evidence closure: every `L(P).nodes[*].evidence_plan` is in `M(P).artifacts.evidence_plans`.
4. Lintability: `dp goal lint`, `dp evidence lint`, `dp loop lint`, and `dp campaign lint` pass
   for generated artifacts when no filesystem collision blocks writing.
5. Conservative readiness: `M(P).state.status == "draft"` and `R(P).needs_refinement == true`
   until a later authoring/refinement process replaces placeholders with implementation-ready
   contracts.

## Non-Goals

1. No semantic campaign planning.
2. No LLM-assisted refinement.
3. No evidence execution.
4. No Beads issue creation.
5. No autonomous campaign running.

## Verification

Required evidence for this slice:

```bash
tmpdir="$(mktemp -d)"
cp tests/fixtures/primary_specs/scaffold_full.md "$tmpdir/primary.md"
(cd "$tmpdir" && dp campaign init --primary-spec primary.md --write --json)
pytest tests/test_campaign_init.py
make check
```
