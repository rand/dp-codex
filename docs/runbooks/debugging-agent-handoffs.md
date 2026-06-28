# Debugging Agent Handoffs

Use stable hints first:

```bash
dp explain DP-HINT-EVIDENCE-FAILED --json
```

For evidence failures:

1. Rerun with `--detail full`.
2. Inspect failed check ids, exit codes, and assertions.
3. Repair the smallest failing surface.
4. Rerun the evidence plan.
5. Verify the goal only after the evidence run matches the current plan.

For no-ready loops, recover campaign state before claiming more work:

```bash
dp campaign status <campaign.json> --json --detail normal
```
