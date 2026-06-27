# ADR-0011: Managed Runs Are Bounded Supervised Adapters

Status: accepted
Date: 2026-06-27
Spec: [SPEC-80.20](../specs/SPEC-80-20-managed-supervised-loop-and-agent-launch-adapters.md)

## Context

SPEC-80 needs dp to let Codex kick off and manage campaign loops and goals. The system already has
manual commands and a one-step supervised handoff, but a caller still has to interpret many stop
conditions itself.

The tempting failure mode is to add a background runner that launches agents, runs evidence, and
interprets completion. That would collapse dp's deterministic control-plane role into an agent
framework and make verification depend on orchestration side effects.

## Decision

Managed run mode is a bounded supervised adapter. It returns a stable stop reason and may claim at
most one ready goal. It does not do agent work.

`dp agent launch` is also a bounded adapter. It claims and starts one GoalContract through dp and
emits the Codex prompt package, but it does not spawn Codex or make completion judgments.

## Consequences

1. Humans and agents get a clearer machine protocol for next action and stop reason.
2. Existing goal, loop, evidence, and recovery commands remain the authority.
3. Future direct process launch can be added behind the same stop conditions if it is still useful.
4. Hooks and CI stay deterministic because neither command belongs in blocking gates.

## Rejected Alternatives

1. **Background runner now.** Rejected because evidence, blockers, and agent execution should stay
   explicit until the supervised protocol has more field use.
2. **Managed run executes evidence automatically.** Rejected because evidence execution is already
   an explicit command and failed evidence should stop the manager.
3. **`agent launch` spawns Codex directly.** Rejected for this slice because process/session
   management is not needed to make the control-plane contract operable.
