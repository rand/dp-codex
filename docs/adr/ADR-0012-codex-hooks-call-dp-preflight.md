# ADR-0012: Codex Hooks Call dp Preflight

Status: accepted
Date: 2026-06-27
Spec: [SPEC-70.03](../specs/SPEC-70-03-codex-integration.md)

## Context

SPEC-80 needs Codex sessions to operate dp-codex through repo artifacts rather than chat memory.
Current Codex supports project-local `AGENTS.md`, `.codex/config.toml`, and `.codex/hooks.json`
layers, but project-local hooks are trust-gated and should remain an explicit adopting-repo choice.

The tempting failure mode is to check in active hooks that run heavyweight gates or make workflow
judgments every time Codex stops. That would increase friction and blur the boundary between
advisory session hygiene and blocking verification.

## Decision

dp owns a deterministic preflight command:

```bash
dp codex preflight --event stop --json
```

Repo-local Codex hook examples may call this command, but dp-codex does not silently install or
enable them. The command is read-only, cheap, JSON-first, and guided by default. `--strict` is
available for repositories that want missing active work or missing evidence signals to block a
hook.

## Consequences

1. Codex integration has a real command surface instead of only prose guidance.
2. Adopting repositories can wire Codex hooks after reviewing and trusting the exact hook config.
3. Hooks remain deterministic and do not call LLMs, run evidence, mutate Beads, or judge completion.
4. Strictness is an operator choice rather than a hidden default.

## Rejected Alternatives

1. **Install active `.codex/hooks.json` in every repo.** Rejected because Codex hook trust should be
   explicit and local to the adopting repository.
2. **Run `make check` from a Codex Stop hook.** Rejected because stop hooks need to stay cheap; full
   gates remain explicit commands and CI checks.
3. **Use hook output as proof of completion.** Rejected because preflight only detects workflow
   hygiene signals. Evidence and verification remain separate dp commands.
