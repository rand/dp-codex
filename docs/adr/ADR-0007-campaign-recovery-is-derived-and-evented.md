---
id: ADR-0007
title: Campaign Recovery Is Derived And Evented
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

Goal events make an individual GoalContract recoverable, but Codex normally works from the campaign
level: it needs to know whether to resume a claim, verify pending evidence, resolve a blocker, or
claim the next ready goal.

Putting that answer in chat would violate SPEC-80. Putting it in a hidden database would make local
recovery harder to audit.

## Decision

Campaign recovery is derived from repo artifacts and append-only event logs:

- CampaignManifest declares the current loop and artifact set.
- LoopLedger plus GoalState events determine node state.
- `campaign status` and `campaign recover` produce a deterministic `resume` object without writing.
- `campaign run --supervised` appends a campaign-level `handoff_claimed` event only when it creates
  a new supervised claim.

The campaign event log starts as JSONL at `.dp/campaigns/events.jsonl`. It records handoff-level
campaign progress, not behavioral proof.

## Consequences

- Future Codex sessions can ask dp what to resume without relying on chat memory.
- Active claimed work is not accidentally bypassed by a new supervised run.
- Stale leases remain recoverable because goal state reconstruction still controls lease semantics.
- Campaign events are audit-friendly and local, but they do not replace GoalState evidence or Beads.
- Later Beads lifecycle synchronization can consume the same resume/event surfaces instead of
  inventing another protocol.
