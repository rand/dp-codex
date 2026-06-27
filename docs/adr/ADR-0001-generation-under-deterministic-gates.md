---
id: ADR-0001
title: Generation Under Deterministic Gates
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

SPEC-80 allows generators to be stochastic, but blocking gates must stay deterministic. Goal
contracts, evidence plans, loop ledgers, hooks, CI, and verification reports are gate surfaces.
If those surfaces call an LLM or rely on model judgment, dp cannot provide local/CI parity or
recoverable state for a future Codex session.

## Decision

Generation and refinement commands may use LLMs only when explicitly invoked as authoring
commands. Blocking gates such as `dp goal lint`, `dp evidence lint`, hooks, CI, and verification
judgments must be deterministic, local, and free of model calls.

Generated artifacts must pass deterministic lint before they can be treated as ready.

## Consequences

- The first GoalContract and EvidencePlan slices implement deterministic lint before any synthesis
  or execution command exists.
- LLM-assisted campaign refinement remains a later authoring feature.
- Validators must return structured errors that can feed a future authoring loop without making
  the model the judge.
