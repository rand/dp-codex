# Instruction Governance

Existing project instructions are local law.

Commands:

```bash
dp instructions inspect --json
dp instructions audit --json
dp instructions plan-update --json
```

`inspect` discovers root and nested `AGENTS.md`, `AGENTS.override.md`, `README.md`,
`CONTRIBUTING.md`, `dp-policy.json`, Codex config/hooks, and repo skills.

`audit` reports missing bootstrap guidance, stale old commands, unsafe bypass language, oversized
instruction files, nested override risk, and skill/hook contradictions.

`plan-update` never mutates. It returns a minimal patch preview and preserves stricter existing
rules. It does not create `AGENTS.override.md`.
