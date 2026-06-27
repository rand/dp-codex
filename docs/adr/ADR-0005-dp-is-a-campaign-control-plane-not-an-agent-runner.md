---
id: ADR-0005
title: dp Is A Campaign Control Plane Not An Agent Runner
status: accepted
created: 2026-06-27
updated: 2026-06-27
superseded_by:
---

## Context

The target workflow needs Codex to ask dp for the next goal, claim it, work it, record evidence, and
route blockers. It does not require dp to become a general autonomous agent framework first.

## Decision

dp is a campaign control plane. It constrains, records, validates, and emits agent-operable
contracts. It does not replace Beads and does not start with a background runner.

## Consequences

- Beads remains the issue and dependency substrate.
- Manual `dp goal ...` and future `dp loop next ...` protocol comes before supervised running.
- Agent prompts are derived from valid contracts and include lifecycle commands.
- A supervised runner is acceptable only as a thin, one-step adapter over the same protocol Codex
  can operate manually.
- `dp campaign run --driver codex --supervised` may claim and emit one handoff, but it must not
  launch Codex, execute evidence, verify completion, or continue in the background.
