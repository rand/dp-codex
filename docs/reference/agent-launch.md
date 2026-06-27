# Agent Launch

`dp agent launch` is a supervised goal-level adapter. It claims and starts one valid GoalContract,
emits the same Codex-operable handoff package as `dp agent prompt`, and stops.

```bash
dp agent launch --goal docs/goals/GOAL-example.json --driver codex --supervised --json
```

The command:

1. requires `--supervised`;
2. supports only `--driver codex` in this slice;
3. validates the GoalContract through the existing goal-emission path;
4. appends a `claimed` goal event with a finite lease;
5. appends a `started` goal event for the same agent;
6. returns the Codex `/goal` text, read-first paths, allowed paths, evidence data, and lifecycle
   commands;
7. returns `autonomous: false` and `launched: false`.

It does not spawn Codex, call an LLM, execute evidence, verify a goal, mutate Beads, or run a
campaign loop.

Useful flags:

1. `--goal <goal.json>`: required GoalContract path.
2. `--driver codex`: required driver value for this slice.
3. `--agent codex`: agent name recorded in goal events.
4. `--lease 2h`: finite claim lease.
5. `--supervised`: required opt-in boundary.
6. `--json`: stable machine-readable output.

Output includes:

```json
{
  "ok": true,
  "command": "agent.launch",
  "mode": "supervised_goal_launch",
  "driver": "codex",
  "supervised": true,
  "autonomous": false,
  "launched": false,
  "goal_id": "GOAL-example",
  "codex_goal": "/goal ...",
  "claim": {"command": "goal.claim"},
  "start": {"command": "goal.start"}
}
```

Exit codes:

1. `0`: the goal was claimed, started, and emitted.
2. `1`: the GoalContract loaded but failed a blocking lifecycle condition, such as an active claim
   by another agent.
3. `2`: missing `--supervised`, unsupported driver, malformed input, invalid GoalContract input,
   missing file, or incomplete command input.

The JSON contract is documented in `/docs/schemas/agent-launch-output.schema.json`.
