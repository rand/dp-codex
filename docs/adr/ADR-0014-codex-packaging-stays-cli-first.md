# ADR-0014: Codex Packaging Stays CLI-First

Status: accepted
Date: 2026-06-27
Spec: [SPEC-70.06](../specs/SPEC-70-06-codex-packaging.md)

## Context

SPEC-80 turns dp into an agent campaign control plane. Codex needs a repeatable way to operate that
control plane: recover campaign state, claim or run the next goal, start work, record evidence,
route blockers, synchronize Beads, and close out with pushed repo artifacts.

dp already has the right execution substrate in the CLI: deterministic commands, stable JSON,
explicit exit codes, append-only event logs, and no hidden state. Codex packaging should reduce
workflow friction without creating a second source of truth or a runtime that is harder to audit
than the CLI.

Codex has several integration surfaces:

1. `AGENTS.md` for durable repo instructions.
2. Skills for reusable task procedures and progressive disclosure.
3. MCP for tool/context servers.
4. Plugins for distributing skills, MCP configuration, hooks, and related assets.
5. Hooks for trusted lifecycle checks.

## Decision

dp-codex will remain CLI-first for SPEC-80 campaign operation. The repository will add a small
repo-local Codex skill, `.agents/skills/dp-campaign-control`, as the minimal packaging scaffold
for repeated Codex use.

The skill is procedural. It tells Codex how to call dp's existing commands, but it does not execute
commands, run model calls, or make verification judgments. The authoritative state and evidence
remain in repo artifacts and dp JSON output.

MCP and plugin packaging are deferred. They require a later ADR that names the specific integration
gap, migration path, trust model, and maintenance owner. Optional hooks remain cheap,
deterministic, and trust-gated; they must not perform LLM calls, broad evidence execution, or
full-repo quality gates.

## Consequences

1. A fresh Codex session can load a compact dp-specific workflow without needing a long prompt.
2. Human users keep the normal CLI workflow and can inspect every command Codex is expected to use.
3. dp avoids maintaining parallel CLI and MCP semantics while the campaign protocol is still
   evolving.
4. Plugin packaging remains available later when the skill, hooks, and any MCP surface are stable
   enough to distribute as a bundle.
5. Verification continues to depend on deterministic dp gates, not agent self-reporting.

## Rejected Alternatives

1. **Ship an MCP server now.** Rejected because current SPEC-80 operations already have stable CLI
   JSON, while MCP would add a long-running server and duplicate command semantics before there is
   a proven need.
2. **Ship a Codex plugin now.** Rejected because plugin distribution is useful once a stable bundle
   exists. At this stage it would mostly package moving instructions.
3. **Use hooks as the primary integration surface.** Rejected because hooks should be cheap
   reminders and preflight checks, not the place where campaign execution, evidence, or model calls
   happen.
4. **Use only `AGENTS.md`.** Rejected because `AGENTS.md` is global repo guidance; a skill gives
   Codex a narrower campaign-control procedure through progressive disclosure.

