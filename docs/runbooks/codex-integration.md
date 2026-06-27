# Codex Integration Runbook

Use this runbook when an adopting repository wants Codex to use dp-codex with minimal repeated
prompting.

## Baseline

1. Add or update repository `AGENTS.md` with the durable workflow expectations:

```md
1. Run `dp doctor --json`.
2. Claim work with `dp task claim --json`, or known work with `dp task claim <id> --json`.
3. Read the returned `context.read_first` files before editing.
4. Run the smallest relevant check first, then `make check` before closeout.
5. Use `dp codex preflight --event stop --json` as a cheap status check.
```

2. Keep project-local Codex config opt-in. Codex loads `.codex/config.toml` and hooks only after the
   project is trusted, and changed hooks must be reviewed and trusted by the operator.

3. Do not put LLM calls, network calls, evidence execution, or full `make check` runs in Codex
   stop hooks. Hooks should call cheap status checks and leave verification to explicit commands.

## Optional Hook Wiring

Copy the examples from `/docs/examples/codex/` into an adopting repository's `.codex/` directory
only after reviewing them:

```bash
mkdir -p .codex
cp docs/examples/codex/hooks.json .codex/hooks.json
```

Then start a new Codex session, open `/hooks`, inspect the project-local hooks, and trust them if
they match the repository's policy.

The default example runs:

```bash
dp codex preflight --event session_start --json
dp codex preflight --event stop --json
```

Use strict mode only when the repo wants Codex stop hooks to block on missing active work or missing
evidence signals:

```bash
dp codex preflight --event stop --strict --json
```

## Human Smoke Test

Run:

```bash
dp doctor --json
dp task claim --json
dp codex preflight --event stop --json
```

A healthy guided response may still contain advisory findings while work is in progress. Before
closing an issue, run the issue's actual evidence commands and `make check`.

## Recovery

If a fresh Codex session has no chat memory:

```bash
dp doctor --json
dp codex preflight --event session_start --json
dp task claim --json
```

If the repo uses campaign artifacts, continue with:

```bash
dp campaign recover docs/campaigns/<campaign>.json --json
dp campaign run docs/campaigns/<campaign>.json --driver codex --supervised --managed --json
```
