# Agent Session Handoff

Before ending:

1. Run the focused checks for the changed slice.
2. Run `make check`.
3. Run `dp agent bootstrap --json --detail brief`.
4. Run any relevant `dp campaign status`, `dp goal status`, or `dp evidence run` command.
5. Record unresolved work as Beads issues or dp blockers.
6. Follow the repository `AGENTS.md` closeout and push rules.

Do not mark a goal complete from narration. Evidence determines done.
