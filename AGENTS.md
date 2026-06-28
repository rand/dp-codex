# Agent Instructions

This repository is developed primarily with Codex. Use these rules to keep execution deterministic and recoverable.

## Operating Principle

Prefer small, independently verifiable increments over large multi-concern changes.

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

## Verification Rules

Run all applicable checks before closing work:

```bash
# Example quality gate pattern
make test
make lint
make typecheck
```

If a command does not exist yet, create a follow-up issue and run the closest equivalent verification.

## Task Close Protocol

1. Verify acceptance criteria from the issue.
2. Close with rationale:
   `bd close <id> --reason "<what was implemented and verified>"`
3. Confirm tracker health:
   `dp doctor --json`
4. Run `dp codex preflight --event stop --json` for a cheap session-status check.
5. Export or back up tracker state only through current Beads commands, such as
   `bd export`, `bd backup sync`, or `bd vc status`.

## Session Completion Protocol

Before ending a session, complete all steps:

```bash
git status
dp doctor --json
bd --readonly status --json
git add <files>
git commit -m "<type>: <summary>"
git push
```

Do not end a session with unpushed committed work unless explicitly instructed.

## Planning Source of Truth

Execution sequencing, milestones, and acceptance criteria are defined in `docs/EXECUTION-PLAN.md`.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   dp doctor --json
   bd --readonly status --json
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
