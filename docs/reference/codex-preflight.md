# Codex Preflight

`dp codex preflight` is a cheap, deterministic status command for Codex session hooks and humans.
It is advisory by default and strict only when explicitly requested.

```bash
dp codex preflight --event session_start --json
dp codex preflight --event stop --json
dp codex preflight --event stop --strict --json
```

The command checks:

1. Beads health using the same read-only provider model as `dp doctor`.
2. In-progress Beads work using `bd --readonly --sandbox list --status in_progress --json -n 0`.
3. Changed files from `git status --porcelain=v1`.
4. Path-based evidence signals from changed tests, docs, and evidence artifacts.

The evidence signal is only a reminder. It is not proof of completion and does not replace
`make check`, `dp evidence run`, or `dp verify --goal`.

## Modes

1. `guided`: missing active work and missing evidence signals are advisory. This is the default for
   low-friction Codex hooks.
2. `strict`: missing active work and missing evidence signals for code/script changes are blocking.

## Exit Codes

1. `0`: no blocking findings.
2. `1`: blocking findings exist.
3. `2`: unsupported event or usage-path failure.

The JSON contract is documented in `/docs/schemas/codex-preflight-output.schema.json`.
