---
id: ADR-0004
title: Decompose Remains Context Fitting Not Semantic Planning
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

`dp decompose` currently splits items by estimated context size and emits a DAG-shaped plan. SPEC-80
needs campaign decomposition that understands specs, decisions, evidence, dependencies, and
blockers.

## Decision

Keep `dp decompose` as context fitting. Do not stretch it into semantic campaign planning.
Campaign compilation will be introduced through explicit `dp campaign` and `dp loop` surfaces with
typed contracts and deterministic lint.

## Consequences

- Existing decompose behavior remains simple and predictable.
- Goal contracts and loop ledgers become the semantic campaign substrate.
- Token-window slicing cannot be mistaken for implementation planning.
