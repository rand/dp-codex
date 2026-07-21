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
6. Treat a failed gate as a completion stop, then follow the bounded recovery ladder before
   declaring a true blocker.
7. Use read-only specialist or adversarial agents for separable diagnosis and review when allowed;
   keep the primary agent responsible for edits, lifecycle, and verification.
```

For machine-global guidance, review and merge
`docs/examples/codex/global-dp-guidance.md` into `~/.codex/AGENTS.md`. Preserve a timestamped backup
of the prior file. Do not overwrite unrelated global instructions.

Record the source commit beside the managed `<!-- dp-agent-discipline:v1 -->` marker, then validate
the installed file from `~/.codex` with `dp instructions audit --json`. Keep the backup checksum in
the implementation receipt. Rollback restores that backup and reinstalls the prior reviewed
dp-codex revision; it never requires deleting unrelated global guidance.

2. Keep project-local Codex config opt-in. Codex loads `.codex/config.toml` and hooks only after the
   project is trusted, and changed hooks must be reviewed and trusted by the operator.

3. Do not put LLM calls, network calls, evidence execution, or full `make check` runs in Codex
   stop hooks. Hooks should call cheap status checks and leave verification to explicit commands.

## Packaging Surface

The default packaging surface is CLI-first:

1. `dp` remains the execution and state API.
2. Repository `AGENTS.md` provides always-visible operating rules.
3. `.agents/skills/dp-campaign-control` provides a repo-local Codex workflow for SPEC-80 campaign
   operation.

Do not add MCP or plugin distribution until a follow-up ADR identifies a concrete gap not served by
the stable CLI JSON protocol and the repo-local skill. See `/docs/runbooks/codex-packaging.md`.

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
