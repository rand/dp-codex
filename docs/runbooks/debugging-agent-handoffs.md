# Debugging Agent Handoffs

Use stable hints first:

```bash
dp explain DP-HINT-EVIDENCE-FAILED --json
```

For evidence failures:

1. Capture the failed receipt, exact command, exit code, branch/HEAD, and GoalContract boundaries.
2. Rerun with `--detail full` and reproduce the smallest deterministic check.
3. Classify the result as `invalid_execution`, `repairable_failure`, `independent_repair`, or
   `true_blocker` using [Agent Recovery and Collaboration](../reference/agent-recovery-and-collaboration.md).
4. Repair the smallest authorized root-cause surface. Do not weaken the gate or repeat an unchanged
   action.
5. Rerun the focused failure, then the evidence plan.
6. Verify the goal only after the evidence run matches the current plan.
7. Block only when no safe in-scope repair remains, required authority is missing, or the declared
   attempt budget is exhausted.

For no-ready loops, recover campaign state before claiming more work:

```bash
dp campaign status <campaign.json> --json --detail normal
```
