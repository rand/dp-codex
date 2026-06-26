# Feature Driver Playbook

Audience: engineers leading multi-step feature delivery.

Goal: deliver predictable outcomes while coordinating specs, tasks, and verification artifacts.

## Planning Pattern

1. Check local health: `dp doctor --json`
2. Claim a bounded task: `bd ready --claim --json` or `bd update <id> --claim`
3. Keep each task one logical outcome.
4. Discover follow-up work immediately when surfaced.

## Execution Pattern

1. Clarify scope with specs and acceptance criteria.
2. Use `dp decompose` when work spans multiple chunks.
3. Maintain trace links as implementation evolves.
4. Use ADRs for consequential design choices.

## Recommended Loop For Each Task

```bash
bd show <id>
dp trace validate --json
dp trace coverage --json
make check
dp enforce pre-commit --policy dp-policy.json --json
```

Then:

```bash
git add .
git commit -m "type: summary"
dp review --json
dp verify --json
dp enforce pre-push --policy dp-policy.json --json
git push
bd close <id> --reason "implemented + verified"
dp doctor --json
bd --readonly status --json
```

## Practical Heuristics

1. If change touches more than three subsystems, split task.
2. If JSON contracts change, update schema and docs in the same commit.
3. If enforcement fails, fix root cause rather than bypassing by default.
4. If a bypass is truly needed, log a specific reason and create follow-up work.

## Common Drift Signals

1. Specs increase but trace coverage does not.
2. Issues close without evidence references.
3. CI checks diverge from local checks.
4. Progress reports become decorative instead of actionable.
