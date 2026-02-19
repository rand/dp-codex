# The Disciplined Loop

DP-Codex is built around one question: can a team deliver reliably without relying on memory, heroics, or a single resident wizard?

## Jobs To Be Done

1. Turn unclear intent into explicit, testable statements.
2. Connect implementation work to declared goals.
3. Decide architecture and tradeoffs with durable records.
4. Detect drift before merge, not after release.
5. Preserve enough context that a fresh session can continue quickly.

## Observe, Orient, Decide, Act (OODA)

### Observe

Inputs become visible:

1. `dp task ready --json`
2. `dp progress --json`
3. `dp trace coverage --json`

The user can see backlog pressure, current repo state, and traceability gaps.

### Orient

Context is shaped into a plan:

1. `dp task show <id>`
2. Spec review (`[SPEC-XX.YY]`) and trace checks
3. Previous progress snapshots and ADR history

This stage is where "what are we really solving" gets answered before typing faster.

### Decide

Decisions become explicit artifacts:

1. `dp adr create ...`
2. `dp decompose ...`
3. Policy selection in `dp-policy.json`

No system removes judgment. This one makes judgment inspectable.

### Act

Execution and verification close the loop:

1. `dp enforce pre-commit`
2. `dp review --json`
3. `dp verify --json`
4. `dp enforce pre-push`
5. `dp task close ...`

When Act fails, the failure is actionable rather than mysterious.

## What "Working Well" Feels Like

1. The next step is obvious from artifacts, not guesswork.
2. A new collaborator can orient in minutes, not hours.
3. Policy blocks the risky path but offers audited emergency exits.
4. CI and local behavior match closely enough that surprises are rare.

If the process feels magical, inspect the files. The magic is usually just good defaults and fewer hidden states.
