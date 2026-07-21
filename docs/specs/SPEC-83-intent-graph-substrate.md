# [SPEC-83.01] Intent-Graph Substrate

## Purpose

Encode the governing maxim at the substrate level: work serves intent; verification disciplines
claims; outcomes settle them. Every goal must show whose intent it serves in the owner's words,
how it contributes to its parent, how it could fail while receipts stay green, and where
real-world outcome contact gets recorded.

Authority over claims is scoped. Outcome signals settle value claims — whether the goal
satisfied the intent it serves — and can always revoke done-as-verified: a `not_useful`
contact unsettles the value claim even when every receipt is green. They never override
correctness or safety verification in the other direction: a useful outcome cannot bless
failing verification. Each authority rules its own claim type.

## Scope

This spec covers the intent-graph capability level of dp-codex:

1. The GoalContract `intent` block schema and its deterministic lint rules.
2. `outcome_contact` lifecycle events, latest-wins confirmation, and digest expiry.
3. Intent re-injection at claim, start, agent launch, and agent bootstrap.
4. The repeated-block hint.
5. `dp graph audit` drift reporting.
6. Root ratification as a durable event (`dp goal ratify`).
7. Adoption gating behind the `docs/reference/intent-graph.md` marker.

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
4. The `parent` key is required (`missing_intent_parent`). Root goals declare `parent: null`;
   `parent: null` with `agent_derived` authorship is lint-legal as a proposed root (see
   Agent-Proposed Roots). Non-root parents must name `goal` and `contribution`
   (`invalid_intent_parent`); `parent_snapshot` is an optional non-empty digest string
   (`invalid_intent_parent_snapshot`).
5. `parent.residual` is audit-only when absent: an absent (or null) residual passes lint and
   surfaces as a `missing_residual` graph-audit warning. A present residual is validated in
   full — a hollow (empty or whitespace) residual fails lint (`invalid_intent_parent`).
6. `defeaters` is audit-only when absent: an absent (or null) `defeaters` field passes lint
   and surfaces as a `missing_defeaters` graph-audit warning. A present `defeaters` field is
   validated in full — a non-list or empty list fails lint (`invalid_intent_defeaters`) and
   hollow entries fail lint (`invalid_intent_defeater`). An evidence-only goal tree is an
   advocacy document; the audit keeps that gap visible without gating.
7. `outcome_contact` must bind `signal` and `channel` (`missing_intent_outcome_contact`,
   `invalid_intent_outcome_contact`).

Mandatory at the intent-graph level: `authorship`, `source`, `verbatim`, `parent` (with
`goal` and `contribution` unless root), and `outcome_contact`. Demoted to audit-only when
absent: `parent.residual` and `defeaters`. Present fields are always validated; absence is
the tolerated state.

## Agent-Proposed Roots

`parent: null` with `authorship: agent_derived` is a lint-legal proposed root: an agent may
draft a root goal without inventing owner authorship. It cannot be pursued until the owner
ratifies it:

1. `dp goal claim` and `dp goal start` refuse such goals with the envelope error
   `unratified_root_goal`: "Agent-proposed root goal awaits owner ratification: set
   authorship to owner_ratified." Claim and start proceed once authorship is `owner` or
   `owner_ratified`.
2. `dp graph audit` lists them as `unratified_root` findings (reporting only; exit 0).
3. `dp goal ratify <goal.json> --json` records ratification as an event. It refuses any goal
   that is not an unratified agent-proposed root (`not_agent_proposed_root`, exit 1) —
   including non-root goals and already-ratified roots. On success it performs exactly one
   goal-file mutation, flipping `intent.authorship` to `owner_ratified` (rewritten with the
   repo goal-file convention: `json.dumps` indent 2, sorted keys, trailing newline), and
   appends a `ratified` event carrying `goal_sha256`, the digest of the post-edit goal file.
   The `ratified` event is orthogonal to lifecycle state, like `outcome_contact`.

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
   claims, outcomes settle them. The supremacy is scoped: outcome signals settle value
   claims and can always revoke done-as-verified, but a useful outcome cannot bless failing
   verification. Each authority rules its own claim type.
5. Outcome recording runs minimal validation only: the goal file must parse as a JSON object
   carrying a non-empty `id`; nothing else. Full goal lint is deliberately not run, so
   outcomes stay zero-friction on historical goals — including intent-less ones — that would
   fail the current lint level.

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
`missing_intent`, `partial_intent`, `missing_residual`, `missing_defeaters`,
`unratified_root`, `unknown_parent_goal`, `invalid_parent_snapshot`,
`stale_parent_snapshot`, `verbatim_not_in_source`, `unreadable_intent_source`,
`duplicate_goal_id`.

1. `missing_residual` and `missing_defeaters` are warning findings for the audit-only fields
   the lint tolerates as absent; a goal carrying either reports intent status `partial`.
   Hollow present fields are lint failures and surface through `partial_intent` instead.
2. `unratified_root` marks agent-proposed roots (`parent: null`, `agent_derived`) awaiting
   owner ratification. It does not change intent status; claim and start refuse such goals.
3. `parent_snapshot`, when present, must match `sha256:[0-9a-f]{64}`; a malformed value is a
   distinct `invalid_parent_snapshot` finding, never reported as stale. Compute snapshots with
   `goal_file_digest` (`dp.core.intent_graph`) over the parent goal file.
4. Staleness compares a well-formed snapshot against the parent goal file's current digest.
5. Duplicate goal ids resolve first-path-wins for the digest: the first file in sorted path
   order under `docs/goals` defines the digest for that goal id; later duplicates do not
   redefine it. Every file involved in a duplicate id is reported with a `duplicate_goal_id`
   finding, and an otherwise-`ok` intent status drops to `partial`.
6. When an intent block carries both a `verbatim` quotation and a `source.path` that resolves
   to an existing file, the audit checks the quotation against the source content:
   whitespace is normalized on both sides (runs of whitespace collapse to single spaces,
   ends stripped) and the quotation must appear as a substring. A miss is a
   `verbatim_not_in_source` warning finding and intent status `partial` — an audit signal,
   never a lint failure. The check is deterministic and calls no LLM. A source file that
   exists but cannot be read as UTF-8 text is the distinct `unreadable_intent_source`
   finding; missing or non-file source paths remain lint findings surfaced via
   `partial_intent`.
7. The audit reports drift; it does not gate. Exit code is always 0.

## Trust Limits

The substrate makes intent visible and auditable; it is not tamper-proof.

1. `source.path` validation is existence plus file-only. Owner-authorship of the cited
   document cannot be machine-verified; it is self-declared via `authorship`.
2. `verbatim` is not checked against the source document by lint; `dp graph audit` performs a
   whitespace-normalized substring check (`verbatim_not_in_source`), which proves only that
   the words appear in the cited document — not their provenance or context. A quotation
   pasted into the source still passes, and a lint-clean goal can carry a fabricated quote
   until the audit runs.
3. All lifecycle events, including `outcome_contact` and `ratified`, are forgeable in the
   local-first trust model: the event log is plain JSONL with no signatures.
4. `dp goal outcome` deliberately requires no active claim and no full lint: the owner
   records contact without a lease, and the goal file only has to parse as a JSON object
   with an id.
5. Ratification gates only roots: once a root is ratified, an agent may author
   `agent_derived` children under it and work them freely — child intent is constrained by
   lint and audit, not by per-child ratification. This is a deliberate tradeoff.
6. Outcome confirmation binds to file content digests: reverting a goal file to a
   previously-confirmed content resurrects the old `useful` confirmation even if a
   `not_useful` was recorded against the intervening edit. Confirmation is
   content-addressed, not history-addressed.

## Invariants

1. A present intent block is always validated; absence fails lint only at the intent-graph
   level. Within a present block, absent `parent.residual` and `defeaters` are audit-only;
   every present field is validated in full.
2. Lint enforcement and adoption classification use the same predicate (marker plus spec81
   surface).
3. `outcome_confirmed` follows the most recent outcome contact recorded against the current
   goal digest.
4. Outcome authority is scoped: outcomes settle value claims and can revoke done-as-verified;
   they never bless failing verification.
5. An unratified agent-proposed root can exist and lint clean but cannot be claimed or
   started; `dp goal ratify` is the governed transition out of that state and applies to
   nothing else.
6. Goal lint, outcome recording, ratification, re-injection, and graph audit never call an
   LLM and never execute goal content.
7. Ratification mutates exactly one goal field (`intent.authorship`) and binds the
   `ratified` event to the post-edit file digest.

## Proof Obligations

1. Tests cover grandfathering below the level, enforcement at the level, and every intent lint
   finding code, including directory and self-citing source paths.
2. Tests cover the residual/defeaters split in both directions: absence passes lint and
   surfaces as `missing_residual`/`missing_defeaters` audit warnings; hollow present fields
   fail lint.
3. Tests cover agent-proposed roots: lint accepts `parent: null` with `agent_derived`
   authorship, claim and start refuse with `unratified_root_goal`, a ratified claim proceeds,
   and the audit reports `unratified_root`.
4. Tests cover confirmation, retraction (useful then not_useful on the unchanged goal), and
   digest expiry of outcome contact.
5. Tests cover receipts counting one per verify cycle and ignoring `evidence_pending`.
6. Tests cover the marker-only repo neither enforcing intent nor classifying `current_spec83`.
7. Tests cover graph audit findings, including `invalid_parent_snapshot` as distinct from
   `stale_parent_snapshot`, without gating.
8. Tests cover the audit verbatim check: an exact match, a miss, a whitespace-differing
   match, and an unreadable (non-UTF-8) source file.
9. Tests cover `duplicate_goal_id` reported on every file sharing an id.
10. Tests cover outcome recording succeeding on an intent-less minimal goal without full
    lint.
11. Tests cover ratify: authorship flips, the `ratified` event binds the post-edit digest,
    claim proceeds afterwards, and non-root or already-ratified goals are refused.

## Non-Goals

SPEC-83.01 does not verify authorship, checks quotation fidelity only as whitespace-normalized
substring presence (audit warning, never a gate), does not sign or protect the event log
against tampering, does not gate on outcome contact, and does not add remote or hosted intent
services.
