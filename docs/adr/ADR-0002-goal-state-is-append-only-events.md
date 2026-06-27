---
id: ADR-0002
title: Goal State Is Append Only Events
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

Codex sessions can end, compact, or restart. Goal state must survive without chat memory and
without a database being introduced before the protocol is understood.

## Decision

Goal lifecycle transitions are recorded as append-only JSONL events under `.dp/goals/events.jsonl`.
State commands reconstruct current state by replaying events for the goal id.

## Consequences

- Recovery is file-based and inspectable.
- Claims can carry finite leases and stale claims can be detected by replay.
- The first implementation avoids hidden state and avoids a database migration.
- Later campaign state can reuse the event pattern or promote it only after the manual protocol is
  proven.
