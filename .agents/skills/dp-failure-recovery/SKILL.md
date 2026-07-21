---
name: dp-failure-recovery
description: Diagnose and recover a failing gate, blocked or stranded dp goal, broken workflow, rescue request, repeated non-evidence retry, or uncertain stop condition.
---

# DP Failure Recovery

Respect `AGENTS.md`, nested instructions, the active GoalContract, and existing claims before acting. A red gate blocks completion, not diagnosis or authorized repair. Proportional verification decides done; verification volume does not.

## Capture

Record the exact command, exit code, failed check, branch/HEAD, worktree state, applicable allowed paths, attempt budget, and failed receipt. Preserve prior evidence.

## Classify in order

1. `invalid_execution`: invocation, environment, cache, lease, worktree, or tool state produced no trustworthy verdict. Repair only non-semantic execution state and rerun the same command.
2. `repairable_failure`: a smallest safe repair is authorized by local law and the active contract.
3. `independent_repair`: the defect is non-semantic but outside the active contract, and another owner or repair goal can fix it without a human semantic or authority decision.
4. `true_blocker`: a new public behavior, schema, exit code, DoD, authority, external dependency, validator, unsafe scope, or exhausted attempt budget is required.

## Repair

For `repairable_failure`, state the hypothesis, make the smallest coherent reversible repair inside allowed paths, rerun the exact failed check, then run required gates. Do not weaken a test, validator, contract, fixture, or evidence assertion. Do not repeat an unchanged action unless relevant state or the hypothesis changed.

For `independent_repair`, preserve the failure and route a bounded follow-up without expanding the active goal. For `true_blocker`, use a supported GoalContract blocker route and keep dp, Beads, reports, and Git state truthful.

## Consult

Use read-only investigator, specialist, or adversarial agents for independent diagnostic threads, domain risk, context pressure, or a failed hypothesis when orchestration is available and allowed. Give each helper a question, read/write scope, forbidden actions, expected output, and stop condition.

One writer owns one worktree. Writing helpers require isolated worktrees and disjoint paths. The primary agent owns lifecycle changes, tracker truth, adopted edits, and verification. External agent output is advisory, cannot establish completion, and must not receive repository material without applicable authorization. Unavailable consultation is not a blocker for otherwise ready work.

## Stop

Stop the affected goal only when no safe discriminating repair remains, required authority is missing, the contract requires an independent repair, or its attempt budget is exhausted. Record the exact reason and next action. Never turn a consultation result or narration into evidence.
