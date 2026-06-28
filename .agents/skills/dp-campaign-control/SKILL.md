---
name: dp-campaign-control
description: Operate SPEC-80-style campaigns through the dp CLI in dp-codex-aware repositories. Use when Codex is asked to continue, recover, claim, run, block, verify, or close out a dp campaign or goal in a repository with `.beads/`, `dp-policy.json`, or instructions that mention dp-codex.
---

# DP Campaign Control

Use dp as the campaign control plane. Codex may reason and edit, but dp owns state, evidence,
blocking gates, and recovery artifacts.

## Start

1. Confirm the repo opts into dp with `.beads/`, `dp-policy.json`, or repo instructions.
2. Run `dp doctor --json`.
3. If a Beads issue is the intake surface, run `dp task claim --json` or claim the known issue.
4. If a campaign is the intake surface, run `dp campaign recover docs/campaigns/<campaign>.json --json`.
5. For the next campaign goal, prefer `dp campaign run docs/campaigns/<campaign>.json --driver codex --supervised --managed --json`.

The managed campaign run claims at most one goal, emits the handoff package, and stops. It does not
spawn Codex, execute evidence, or mark work complete.

## Work a Goal

1. Read the handoff's `read_first` files before editing.
2. Start the goal with `dp goal start docs/goals/<goal>.json --agent codex --json`.
3. Stay inside the handoff boundaries and GoalContract allowed paths.
4. Run the smallest relevant check first.
5. Repair local failures before broadening to `make check`.
6. Use `dp evidence run docs/evidence/<evidence>.json --output docs/evidence-runs/<run>.json --json` when the goal has an evidence plan.
7. Use `dp verify --goal docs/goals/<goal>.json --evidence docs/evidence-runs/<run>.json --json` before claiming completion.
8. Use `dp campaign sync-beads docs/campaigns/<campaign>.json --write --json` when campaign state needs to reconcile back to Beads.

## Block or Release

Block through dp when a required spec, decision, validator, or scope change is missing:

```bash
dp goal block docs/goals/<goal>.json --reason needs_decision --write-artifact --json
```

Use the GoalContract blocker routes: `needs_specification`, `needs_decision`, `needs_validator`,
`unsafe_scope`, or `budget_exhausted`.

Release the goal instead of leaving an invisible claim when stopping without completion:

```bash
dp goal release docs/goals/<goal>.json --reason "context reset" --json
```

## Close Out

Before ending the session:

1. Run the focused tests for the changed slice.
2. Run `make check`.
3. Run `dp doctor --json`.
4. Run `bd --readonly status --json`.
5. Close or update the Beads issue with evidence.
6. Commit and push.
7. Confirm `git status` reports the branch is up to date with origin.

## Boundaries

Do not mark completion from agent narration.
Do not execute raw shell from generated JSON.
Do not call an LLM from hooks, validators, evidence assertions, or CI.
Do not spawn Codex from dp in this workflow.
Do not replace Beads with campaign files; synchronize through explicit dp or bd commands.
