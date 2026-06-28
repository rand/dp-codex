---
name: dp-hook-triage
description: Audit hook failures; trigger on hook failed, Codex hook, git hook.
---

# dp-hook-triage

Respect `AGENTS.md` and any nested `AGENTS.md` before using this skill.

When to use: Use for deterministic local hook triage only.

When not to use: unrelated repositories that have not opted into dp-codex.

First command: Run `dp hooks audit --json` before changing hook files.

Keep work scoped, prefer compact JSON detail first, and expand only when needed.
