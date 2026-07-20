# [SPEC-83.01] Intent-Graph Substrate

## Purpose

Encode the governing maxim at the substrate level: work serves intent; verification disciplines
claims; outcomes settle them. Every goal must show whose intent it serves in the owner's words,
how it contributes to its parent, how it could fail while receipts stay green, and where
real-world outcome contact gets recorded.

## Scope

This spec covers the intent-graph capability level of dp-codex:

1. The GoalContract `intent` block schema and its deterministic lint rules.
2. `outcome_contact` lifecycle events, latest-wins confirmation, and digest expiry.
3. Intent re-injection at claim, start, agent launch, and agent bootstrap.
4. The repeated-block hint.
5. `dp graph audit` drift reporting.
6. Adoption gating behind the `docs/reference/intent-graph.md` marker.

## Adoption Level

The intent-graph level is active when the repo carries the marker file
`docs/reference/intent-graph.md` AND the SPEC-81 reference surface
(`docs/reference/agent-response-contract.md`, `docs/reference/toolcards.md`,
`docs/reference/hint-codes.md`). Lint enforcement (`intent_enforcement_active`) and adoption
classification (`dp adopt inspect` signal `has_spec83`, classification `current_spec83`) share
this one predicate; a marker without the spec81 surface neither enforces nor classifies.

Grandfathering: below the level, a goal without an `intent` block lints clean. A present
`intent` block is always validated in full, at any level.

## Intent Block

```json
{
  "intent": {
    "authorship": "owner | agent_derived | owner_ratified",
    "source": {"path": "docs/vision.md", "anchor": "doctor"},
    "verbatim": "Exact owner words this goal serves.",
    "parent": {
      "goal": "GOAL-ROOT",
      "contribution": "How this child serves the parent.",
      "residual": "What of the parent this child does not capture.",
      "parent_snapshot": "sha256:<64-hex digest of the parent goal file>"
    },
    "defeaters": ["How the goal could be unsatisfied while receipts stay green."],
    "outcome_contact": {
      "signal": "Real-world signal that settles the goal.",
      "channel": "docs/outcomes/doctor.md"
    }
  }
}
```

Lint rules (`dp goal lint`):

1. `authorship` must be one of `owner`, `agent_derived`, `owner_ratified`
   (`invalid_intent_authorship`).
2. `source.path` must be a sane repo-relative path (`invalid_intent_source_path`) that exists
   (`intent_source_not_found`), is a file rather than a directory (`intent_source_not_a_file`),
   and is not the goal contract itself (`intent_source_self_citation`). `source.anchor` is an
   optional non-empty string (`invalid_intent_source_anchor`). A missing source object is
   `missing_intent_source`: intent must cite an existing source document; authorship is
   declared, not verified.
3. `verbatim` must be a non-empty quotation (`missing_intent_verbatim`).
4. The `parent` key is required (`missing_intent_parent`). Root goals declare `parent: null`
   and require `owner` or `owner_ratified` authorship
   (`intent_root_requires_owner_authorship`). Non-root parents must name `goal`,
   `contribution`, and `residual` (`invalid_intent_parent`); `parent_snapshot` is an optional
   non-empty digest string (`invalid_intent_parent_snapshot`).
5. `defeaters` must be a non-empty list of non-empty strings (`missing_intent_defeaters`,
   `invalid_intent_defeater`). An evidence-only goal tree is an advocacy document.
6. `outcome_contact` must bind `signal` and `channel` (`missing_intent_outcome_contact`,
   `invalid_intent_outcome_contact`).

## Outcome Contact

`dp goal outcome <goal.json> --class useful|mixed|not_useful --ref <governed-ref>` appends an
`outcome_contact` event carrying the class, the ref, and `goal_sha256`, the digest of the goal
file at recording time.

1. Confirmation is latest-wins, consistent with `last_outcome`: `outcome_confirmed` (reported
   by `dp goal verify`) is true iff the most recent `outcome_contact` event whose `goal_sha256`
   matches the current goal digest has class `useful` or `mixed`. A later `not_useful` on the
   unchanged goal retracts an earlier confirmation.
2. Digest expiry: editing the goal file invalidates confirmation; outcome contact confirms only
   the goal content it was recorded against.
3. `receipts_since_last_outcome_contact` counts only `verified` events — one receipt per verify
   cycle; `evidence_pending` is not a receipt. It is null before the first outcome contact and
   resets to 0 on each contact.
4. `outcome_confirmed` never gates or substitutes for `verified`; verification disciplines
   claims, outcomes settle them.

## Re-Injection Points

`dp goal claim`, `dp goal start`, `dp agent launch`, and `dp agent bootstrap` re-inject the
goal's `verbatim` quotation, `source` citation, and parent `contribution` exactly as authored,
so re-encoding points re-anchor on owner words, not paraphrase.

## Repeated-Block Hint

The 2nd and subsequent `blocked` events since the last claim surface
`DP-HINT-GOAL-REPEATED-BLOCKS`, asking for a path-to-root restatement in the owner's words. It
is a nudge in the response envelope, not a gate.

## Graph Audit

`dp graph audit --json` walks `docs/goals/*.json` and reports per goal: intent status
(`ok`, `partial`, `missing`, `unreadable`), findings, `receipts_since_last_outcome_contact`,
`last_outcome_class`, and the parent goal id. Finding codes: `malformed_goal`,
`missing_intent`, `partial_intent`, `empty_defeaters`, `unknown_parent_goal`,
`invalid_parent_snapshot`, `stale_parent_snapshot`.

1. `parent_snapshot`, when present, must match `sha256:[0-9a-f]{64}`; a malformed value is a
   distinct `invalid_parent_snapshot` finding, never reported as stale. Compute snapshots with
   `goal_file_digest` (`dp.core.intent_graph`) over the parent goal file.
2. Staleness compares a well-formed snapshot against the parent goal file's current digest.
3. Duplicate goal ids resolve first-path-wins: the first file in sorted path order under
   `docs/goals` defines the digest for that goal id; later duplicates are audited as goals but
   do not redefine the id.
4. The audit reports drift; it does not gate. Exit code is always 0.

## Trust Limits

The substrate makes intent visible and auditable; it is not tamper-proof.

1. `source.path` validation is existence plus file-only. Owner-authorship of the cited
   document cannot be machine-verified; it is self-declared via `authorship`.
2. `verbatim` is not checked against the source document content; a quotation can be wrong or
   fabricated and still lint clean.
3. All lifecycle events, including `outcome_contact`, are forgeable in the local-first trust
   model: the event log is plain JSONL with no signatures.
4. `dp goal outcome` deliberately requires no active claim: the owner records contact without
   a lease.

## Invariants

1. A present intent block is always validated; absence fails lint only at the intent-graph
   level.
2. Lint enforcement and adoption classification use the same predicate (marker plus spec81
   surface).
3. `outcome_confirmed` follows the most recent outcome contact recorded against the current
   goal digest.
4. Goal lint, outcome recording, re-injection, and graph audit never call an LLM and never
   execute goal content.

## Proof Obligations

1. Tests cover grandfathering below the level, enforcement at the level, and every intent lint
   finding code, including directory and self-citing source paths.
2. Tests cover confirmation, retraction (useful then not_useful on the unchanged goal), and
   digest expiry of outcome contact.
3. Tests cover receipts counting one per verify cycle and ignoring `evidence_pending`.
4. Tests cover the marker-only repo neither enforcing intent nor classifying `current_spec83`.
5. Tests cover graph audit findings, including `invalid_parent_snapshot` as distinct from
   `stale_parent_snapshot`, without gating.

## Non-Goals

SPEC-83.01 does not verify authorship or quotation fidelity, does not sign or protect the
event log against tampering, does not gate on outcome contact, and does not add remote or
hosted intent services.
