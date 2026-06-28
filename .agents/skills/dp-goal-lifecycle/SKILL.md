---
name: dp-goal-lifecycle
description: Manage goal state; trigger on start, block, release, verify, lease.
---

# dp-goal-lifecycle

Respect `AGENTS.md` and any nested `AGENTS.md` before using this skill.

When to use: Use for GoalContract lifecycle transitions.

When not to use: unrelated repositories that have not opted into dp-codex.

First command: Run `dp goal status <goal.json> --json --detail brief` before changing state.

Keep work scoped, prefer compact JSON detail first, and expand only when needed.
