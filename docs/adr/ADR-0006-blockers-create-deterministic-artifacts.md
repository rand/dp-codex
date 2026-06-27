---
id: ADR-0006
title: Blockers Create Deterministic Artifacts
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

SPEC-80 requires campaign state to survive agent sessions. A structured `blocked` event is useful,
but a blocked agent also needs the next disciplined artifact: a spec when requirements are missing,
an ADR when a decision is missing, or an EvidencePlan when validation is missing.

Without artifact routing, blockers are still too easy to lose in a transcript.

## Decision

`dp goal block --write-artifact` resolves the GoalContract's `blocked_routes` entry for the
selected reason, writes one deterministic route artifact, optionally creates a Beads follow-up, and
records the routing result in the append-only goal event.

The route is local, explicit, and deterministic:

- `needs_specification` uses `create_spec_stub`.
- `needs_decision` uses `create_adr_stub`.
- `needs_validator` uses `create_evidence_stub`.

The command does not call an LLM, does not execute generated shell, and does not hide Beads or
artifact failures. A valid blocked event is still durable even if route artifact creation fails.

## Consequences

- Future Codex sessions can recover not only that a goal blocked, but which artifact was created to
  resolve the blocker.
- Beads remains the follow-up and dependency substrate rather than being replaced by dp state.
- Missing or unsupported routes become explicit command failures instead of inert prose.
- Artifact collisions are safe: identical deterministic stubs can be reused, but changed stubs are
  never overwritten.
- `goal block` becomes the first route from agent uncertainty back into the disciplined process.
