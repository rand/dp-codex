# SPEC-70.06 Codex Packaging and Integration Surface

Status: active
Issue: dpcx-ea9.5
Parent: SPEC-80.22

[SPEC-70.06]

## Intent

SPEC-80 only works in practice if Codex can discover and operate dp's campaign-control protocol
without a long preamble in every session. The integration surface must reduce repeated agent
friction while preserving dp's safety model: deterministic gates, stable JSON, explicit exit codes,
no hidden state, no arbitrary shell execution from generated JSON, and no LLM calls in hooks,
validators, or CI.

This spec decides the packaging path for Codex-facing dp usage across four candidates:

1. CLI plus repository `AGENTS.md`.
2. Repo-local Codex skill.
3. MCP server.
4. Codex plugin.

## Requirements

1. dp MUST remain usable as a normal CLI in any adopting repository that opts in with `.beads/`,
   `dp-policy.json`, or repo instructions.
2. The recommended packaging surface MUST support the SPEC-80 loop: doctor, recover, run or claim,
   start, verify evidence, block, release, sync Beads, and close out with pushed artifacts.
3. The packaging surface MUST NOT introduce network-dependent runtime behavior; the intended
   scaffold has no network dependency.
4. The packaging surface MUST NOT move verification judgment into Codex narration, hooks, or model
   calls.
5. The packaging surface MUST be safe for repo-local trust: an operator can inspect it before use,
   and it does not execute commands by itself.
6. MCP and plugin packaging MUST be explicitly justified before implementation because they add
   distribution, trust, versioning, and maintenance surfaces beyond the CLI.

## Candidate Comparison

| Surface | Strength | Risk | Maintenance Cost | Decision |
| --- | --- | --- | --- | --- |
| CLI + `AGENTS.md` | Stable, already tested, works in shells and CI, no new runtime | Repeated procedural knowledge can still be lost between sessions | Low | Keep as baseline |
| Repo-local Codex skill | Encodes reusable agent procedure with progressive disclosure and no runtime | Only helps Codex surfaces that load skills | Low | Add now |
| MCP server | Native tool/context API for richer interactive integrations | Long-running server, trust boundary, auth/config, duplicate command semantics | Medium/high | Defer |
| Codex plugin | Portable bundle for skills, MCP config, hooks, and app mappings | Premature distribution layer while protocol still evolves | Medium | Defer |
| Hooks | Cheap lifecycle reminders for trusted repos | Easy to over-enforce or hide slow checks in editor loops | Low/medium | Keep optional and deterministic |

## Decision

The minimal useful integration surface is:

1. **CLI-first operation.** `dp` remains the source of truth for campaign state, goal lifecycle,
   evidence, Beads reconciliation, and stable JSON reports.
2. **Repository instructions.** `AGENTS.md` remains the always-visible bootstrap for dp-aware repos.
3. **Repo-local Codex skill.** `.agents/skills/dp-campaign-control/SKILL.md` provides a compact
   Codex procedure for SPEC-80 campaign operation. It contains no scripts, no MCP config, no hooks,
   and no network dependency.
4. **Deferred MCP/plugin packaging.** MCP and plugin work require a follow-up ADR that identifies
   a concrete integration need not served by CLI JSON plus the skill.

This keeps the first packaging step boring on purpose. It makes the next Codex session better
without adding a second execution protocol.

## Safety Invariant

Let `A` be an agent using the skill, `C` be the dp CLI, and `G` be any blocking gate. The packaging
surface is acceptable only if:

```text
G's result is a deterministic function of repo artifacts and command outputs,
not a function of A's natural-language judgment.
```

The skill may tell Codex which commands to run. It does not make the result true.

## User Experience

A human user should be able to say:

```text
Use the dp campaign-control skill and continue this campaign.
```

Codex should then:

1. Run `dp doctor --json`.
2. Recover campaign state if a campaign path is known.
3. Run the supervised managed handoff or claim the known Beads issue.
4. Start the goal through dp.
5. Work inside the emitted boundaries.
6. Run evidence and `dp verify --goal`.
7. Block through dp when a spec, ADR, validator, or Beads follow-up is missing.
8. Sync Beads and push only after checks pass.

## Non-Goals

1. Do not add an MCP server in this slice.
2. Do not package a Codex plugin in this slice.
3. Do not add or modify blocking hooks in this slice.
4. Do not use network calls or model calls in any packaging gate.
5. Do not make the skill a substitute for `dp goal lint`, `dp evidence run`, or `dp verify --goal`.

## Verification

Required checks:

```bash
pytest tests/test_codex_packaging_docs.py
make check
dp doctor --json
bd --readonly status --json
```
