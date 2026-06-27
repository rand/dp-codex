---
id: ADR-0008
title: dp Owns Evidence Run Artifacts
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

SPEC-80 requires evidence, not narration, to advance campaign state. Before SPEC-80.17, `dp
evidence run` emitted JSON to stdout and relied on a human or agent to redirect it to a file. That
kept the executor simple, but it left the most important artifact path outside dp's contract.

Agents need exact commands. Humans need one canonical happy path. Future recovery needs stable
evidence locations and provenance.

## Decision

dp will own evidence-run artifact creation.

`dp evidence run --output <run.json>` validates a sane relative JSON path before any checks run,
refuses accidental overwrites unless `--force` is explicit, writes the same evidence-run payload
that `dp goal verify` already consumes, and keeps evidence execution behind SPEC-80.08's
registered-command executor.

`dp verify --goal <goal.json>` becomes the deterministic orchestration command for the human and
agent happy path. It may run evidence and write an artifact, or it may validate a supplied run
artifact, but it delegates the final state transition to the existing `dp goal verify` predicate.

## Consequences

- Handoffs can name concrete evidence paths instead of `<run.json>`.
- The top-level `dp verify` command now has two modes: legacy manifest verification and goal
  orchestration via `--goal`.
- Evidence-run artifacts are mutable latest-run files unless callers choose unique paths; verified
  events record the artifact hash at verification time.
- Hooks and CI remain free to use legacy `dp verify --json` without executing goal evidence.
