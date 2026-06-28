---
name: dp-agent-bootstrap
description: Orient in a dp-codex-aware repo; trigger on first command, opened repo, bootstrap, where to start.
---

# dp-agent-bootstrap

Respect `AGENTS.md` and any nested `AGENTS.md` before using this skill.

When to use: Use when entering or resuming a repository.

When not to use: unrelated repositories that have not opted into dp-codex.

First command: Run `dp agent bootstrap --json --detail brief` first.

Keep work scoped, prefer compact JSON detail first, and expand only when needed.
