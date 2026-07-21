# Agent Instructions

This repository is developed primarily with Codex. Use these rules to keep execution deterministic and recoverable.

## Operating Principle

Safety, versioning, trackers, and verification exist to enable fast, powerful work with clean
branch, inspection, and revert semantics. They are support machinery, not the product. Prefer
small, independently useful increments over large multi-concern changes.

## Outcome and Verification Budget

- Name the useful change in the real system before adding process work.
- Plans, tracker updates, receipts, evidence files, reviews, and summaries do not substitute for
  the outcome they support.
- Before adding a check or artifact, name the decision or failure risk it changes. If it changes
  neither, skip it.
- Use the smallest proportional proof: normally a focused check, any repository-required gate,
  and one live observation for a live change. Add checks only for an identified risk or a failure.
- Once the outcome works and named risks are answered, stop verifying and ship.
- If administration or verification consumes more effort than implementation, cut it back unless
  the task is itself an audit, recovery, or high-consequence boundary.

## Work Intake

1. Run `dp doctor --json` to confirm Beads and local workflow health.
2. Pull and claim ready work with `dp task claim --json`, or claim a known issue with `dp task claim <id> --json`.
3. Read the returned `context.read_first` files before editing.

## Agent Experience

1. Start agent sessions with `dp agent bootstrap --json --detail brief` for compact local orientation.
2. Use `dp agent capabilities --json` when command safety, mutability, or next actions are unclear.
3. Treat dp hints as workflow affordances; this file and nested `AGENTS.md` files remain project law.

## Implementation Rules

1. Keep each issue scoped to one logical outcome.
2. Add or update tests in the same change when behavior changes.
3. Keep commands reproducible (`make`, scripts, or explicit one-liners).
4. Avoid introducing hidden state in tooling; prefer explicit config files.

<!-- dp-agent-discipline:v1 -->

## Recovery and Escalation

1. A failed gate blocks completion, not diagnosis or authorized repair.
2. Capture the exact failure and classify it before declaring a blocker: invalid execution,
   repairable in-scope failure, independent repair, or true decision/authority/scope blocker.
3. Make the smallest coherent reversible repair allowed by project law, then rerun the focused
   check and required gates. Never weaken evidence to obtain green.
4. Do not repeat an unchanged action unless relevant state or the hypothesis changed. Respect the
   GoalContract attempt budget when present.
5. Route a durable blocker only when no safe in-scope repair remains or new authority is required.
   Proportional verification decides done; verification volume does not.

## Agent Collaboration

1. Use specialist or adversarial agents proactively for independent diagnosis, domain risk,
   context pressure, or fresh review when orchestration is available and project law allows it.
2. Give each helper a bounded question, read/write scope, forbidden actions, expected output, and
   stop condition. Default helpers to read-only.
3. One writer owns one worktree. Writing helpers require isolated worktrees and disjoint paths.
4. The primary agent owns decisions, lifecycle and tracker changes, integrated edits, and
   verification. External agent output is advisory and cannot establish completion.

## Verification Rules

Run the focused check for the changed behavior and the repository-required gate before closing
work:

```bash
# Example quality gate pattern
make test
make lint
make typecheck
```

Do not create speculative follow-up issues or run unrelated checks merely to increase verification
volume.

## Task Close Protocol

1. Verify acceptance criteria from the issue.
2. Close with rationale:
   `bd close <id> --reason "<what was implemented and verified>"`
3. Export or back up tracker state only when tracker state changed, using current Beads commands
   such as
   `bd export`, `bd backup sync`, or `bd vc status`.
4. Commit and push completed work. If an external authority or remote policy prevents push after
   diagnosis, report that blocker rather than retrying unchanged.

## Planning Source of Truth

Execution sequencing, milestones, and acceptance criteria are defined in `docs/EXECUTION-PLAN.md`.
