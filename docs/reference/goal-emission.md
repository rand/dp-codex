# Goal Emission

Goal emission formats a valid GoalContract into an agent-operable prompt.

Commands:

```bash
dp goal emit <goal.json> --format codex --json
dp agent prompt --goal <goal.json> --format codex --json
```

The Codex format includes:

1. Objective.
2. Evidence cues.
3. Read-first files.
4. Allowed paths.
5. Allowed command cues.
6. Iteration policy.
7. Blocked-stop condition.
8. `dp goal start`, `heartbeat`, `complete`, `block`, and `release` commands.

Emission does not execute evidence, call an LLM, or decide completion.
