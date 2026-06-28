# SPEC-80.09 Semantic Primary Spec Compiler

Status: active
Issue: dpcx-pb5.9.1
Parent: SPEC-80

[SPEC-80.09]

Implementation note, 2026-06-27: SPEC-80.11 consumes these deterministic compiler signals through
`dp campaign refine`, which can write child spec/ADR stubs, GoalContract/EvidencePlan refinement
metadata, and explicit Beads work while keeping the campaign draft.

## Intent

The first campaign compiler was intentionally mechanical: Markdown headings became draft
GoalContracts plus `needs_refinement` markers. That made campaigns recoverable, but left future
Codex sessions with too little explanation about why a node exists, what evidence was visible, and
what is still missing.

This slice adds deterministic semantic-signal extraction to `dp campaign init`. It is not an LLM
planner and does not claim implementation readiness. It makes the draft campaign more useful by
recording local signals from the primary spec:

1. requirement cues
2. evidence and validation cues
3. decision and risk cues
4. blocker cues
5. dependency cues
6. node classification and refinement state

The output remains a draft campaign until later authoring work turns these signals into child
specs, ADRs, validators, Beads work, and final GoalContracts that pass deterministic gates.

## Command

```bash
dp campaign init --primary-spec <path> --write --json
```

## Requirements

1. `dp campaign init` MUST continue to accept only sane local relative primary-spec paths.
2. The compiler MUST be deterministic over the primary spec bytes and current dp versioned rules.
3. The compiler MUST NOT call an LLM.
4. The compiler MUST NOT create Beads issues.
5. The compiler MUST NOT execute evidence.
6. The compiler MUST NOT infer dependency edges from prose.
7. The compiler MUST extract section-local signal cues from Markdown text outside fenced code
   headings.
8. The compiler MUST classify each generated node as one of:
   1. `implementation`
   2. `evidence`
   3. `decision`
   4. `context`
   5. `unknown`
9. The compiler MUST assign each generated node a refinement state:
   1. `implementation_candidate`
   2. `evidence_candidate`
   3. `needs_decision`
   4. `needs_validator`
   5. `needs_specification`
10. The compiler MUST expose a stable top-level `compiler` object in JSON output containing:
    1. mode
    2. LLM-free and semantic-planning flags
    3. summary counts
    4. node analyses
11. Generated CampaignManifest, LoopLedger, GoalContract, and `needs_refinement` artifacts MUST
    carry enough compiler provenance for a future Codex session to explain why the campaign is
    still draft.
12. The campaign state MUST remain `draft`.
13. Existing deterministic lint gates MUST continue to pass for generated artifacts.
14. Signal cues in public compiler JSON MUST be bounded excerpts. The primary spec is the source of
    truth; campaign-init output summarizes and points, it does not paste unbounded source
    paragraphs back into the agent context.

## Formal Invariants

Let `P` be the primary spec text, `S(P)` the ordered section list, and `A(P)` the compiler analysis.

1. Determinism:
   `P1 == P2 => A(P1) == A(P2)`.
2. No hidden authoring:
   `A(P).llm == false` and `A(P).semantic_planning == false`.
3. No false graph inference:
   dependency prose may appear only in `signals.dependencies`; it MUST NOT become a LoopLedger
   `depends_on` edge in this slice.
4. Draft preservation:
   `campaign.state.status == "draft"` for every generated campaign.
5. Evidence humility:
   evidence cues can justify `implementation_candidate` or `evidence_candidate`, but they are not
   proof and MUST NOT create `verified` state.
6. Refined recoverability:
   every generated GoalContract and loop node references its compiler classification or refinement
   state so a future session can recover why the node exists without chat memory.
7. Bounded context:
   for every signal cue `c` emitted by the compiler, `len(c) <= 220`.

## Non-Goals

1. No LLM-assisted campaign refinement.
2. No ADR or child-spec authoring.
3. No Beads issue generation.
4. No evidence execution.
5. No supervised runner.
6. No automatic dependency graph inference from prose.

## Verification

Required evidence for this slice:

```bash
pytest tests/test_campaign_init.py tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
```

## Realistic Primary-Spec Benchmark

The compiler has been checked against local Waveguide- and Supastructure-style primary specs. Those
specs exposed the main hardening requirement for this slice: large architecture specs can contain
long paragraph-level evidence, decision, and dependency cues, and the dry-run JSON must remain
compact enough for human and agent users. The benchmark expectation is not semantic readiness; it
is deterministic, lint-valid, bounded output that preserves draft status and identifies the need for
refinement.
