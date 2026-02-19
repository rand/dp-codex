# Quickstart: Ship Your First Feature

Audience: new contributors or teammates adopting DP-Codex for the first time.

Goal: go from "what is this" to a completed task with traceability and verification.

## 1. Bootstrap

```bash
uv sync --dev
bd ready
./hooks/install.sh
make check
```

If this passes, your environment is healthy.

## 2. Pick A Task

```bash
bd ready
bd update <issue-id> --status in_progress
bd show <issue-id>
```

Read acceptance criteria before editing. Future you will appreciate past you.

## 3. Connect Intent To Implementation

1. Add or update spec IDs in docs: `[SPEC-XX.YY]`
2. Add `@trace SPEC-XX.YY` markers in code/tests where behavior is implemented.

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
dp review --json
dp verify --json
dp enforce pre-push --policy dp-policy.json --json
git push
```

## 7. Close The Task

```bash
bd close <issue-id> --reason "what changed and what was verified"
bd sync
```

You now have a complete, auditable loop from intent to closure.
