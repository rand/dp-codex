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

`audit` reports missing bootstrap, recovery, or collaboration guidance; stale old commands; unsafe
bypass language; oversized instruction files; nested override risk; and skill/hook contradictions.

`plan-update` never mutates. It returns a minimal additive patch preview for any missing bootstrap,
recovery, or collaboration sections and preserves stricter existing rules. It does not create
`AGENTS.override.md`.

Recovery guidance does not weaken a gate. It distinguishes the prohibition on claiming completion
from the authority to diagnose and repair inside existing project law. Collaboration guidance keeps
helpers advisory and leaves lifecycle and verification ownership with the primary agent.
