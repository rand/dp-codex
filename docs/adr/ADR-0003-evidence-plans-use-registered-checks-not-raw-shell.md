---
id: ADR-0003
title: Evidence Plans Use Registered Checks Not Raw Shell
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

SPEC-80 requires evidence to determine progress, but generated JSON must not become an arbitrary
shell executor. The first slice only lints and records evidence references; future evidence
execution is security-sensitive.

## Decision

Evidence execution will use typed check objects, argv arrays, explicit timeouts, success exit
codes, and registered or allowlisted commands. Raw shell strings with control operators are
invalid in structured evidence fields.

Goal lint may accept declarative verification command cues for human/Codex readability, but it
rejects shell control operators and never executes them.

## Consequences

- `dp goal complete` records evidence as `evidence_pending` until evidence validation exists.
- Future `dp evidence run` must not use `shell=True`.
- Lint can block unsafe generated evidence before any executor exists.
