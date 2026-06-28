---
name: dp-instruction-governance
description: Respect and audit instructions; trigger on AGENTS.md, override, local law.
---

# dp-instruction-governance

Respect `AGENTS.md` and any nested `AGENTS.md` before using this skill.

When to use: Use before editing project instruction files.

When not to use: unrelated repositories that have not opted into dp-codex.

First command: Run `dp instructions inspect --json` and then `dp instructions audit --json`.

Keep work scoped, prefer compact JSON detail first, and expand only when needed.
