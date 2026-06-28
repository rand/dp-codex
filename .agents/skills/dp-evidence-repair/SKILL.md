---
name: dp-evidence-repair
description: Repair evidence failures; trigger on failed check, stale run, missing validator.
---

# dp-evidence-repair

Respect `AGENTS.md` and any nested `AGENTS.md` before using this skill.

When to use: Use when deterministic evidence blocks completion.

When not to use: unrelated repositories that have not opted into dp-codex.

First command: Run `dp explain DP-HINT-EVIDENCE-FAILED --json` and inspect full evidence detail.

Keep work scoped, prefer compact JSON detail first, and expand only when needed.
