# Skills

Repo-scoped Codex skills live under `.agents/skills/`.

Commands:

```bash
dp skills scaffold --target repo --json
dp skills lint --json
dp skills audit --json
dp skills eval --json
```

SPEC-81 skills are small workflow capsules. Each skill must have one job, trigger-rich metadata,
compact body text, and explicit `AGENTS.md` precedence.

Initial skills:

- `dp-agent-bootstrap`
- `dp-campaign-control`
- `dp-goal-lifecycle`
- `dp-evidence-repair`
- `dp-adoption-migration`
- `dp-instruction-governance`
- `dp-session-handoff`
- `dp-hook-triage`
