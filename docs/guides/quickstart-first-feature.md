# Quickstart: Ship Your First Feature

Audience: new contributors or teammates adopting DP-Codex for the first time.

Goal: go from "what is this" to a completed task with traceability and verification.

## 1. Bootstrap

```bash
uv sync --dev
dp doctor --json
dp task ready --json
./hooks/install.sh
make check
```

If this passes, your environment is healthy.

## 2. Pick A Task

```bash
dp task claim --json
dp task show <issue-id> --json
```

If you already know the issue ID, claim it with `dp task claim <issue-id> --json`.

Read acceptance criteria before editing. Future you will appreciate past you.

## 3. Connect Intent To Implementation

1. Add or update spec IDs in docs: `[SPEC-XX.YY]`
2. Add `@trace SPEC-XX.YY` markers in code/tests where behavior is implemented.
3. If your task includes a GoalContract, validate it before editing:

```bash
dp goal lint docs/goals/GOAL-example.json --json
```

Validate:

```bash
dp trace validate --json
dp trace coverage --json
```

## 4. Record Decisions When Needed

```bash
dp adr create "Short decision title" --json
```

Use ADRs when design alternatives are non-trivial.

## 5. Run Quality And Enforcement

```bash
make check
dp enforce pre-commit --policy dp-policy.json --json
```

## 6. Commit, Verify, Push

```bash
git add .
git commit -m "feat: concise summary"
dp codex preflight --event stop --json
dp review --json
dp verify --json
dp enforce pre-push --policy dp-policy.json --json
git push
```

## 7. Close The Task

```bash
bd close <issue-id> --reason "what changed and what was verified"
dp doctor --json
bd --readonly status --json
```

You now have a complete, auditable loop from intent to closure.
