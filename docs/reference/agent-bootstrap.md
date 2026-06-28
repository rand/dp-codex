# Agent Bootstrap

`dp agent bootstrap --json --detail brief` is the canonical first command for agents in a
dp-aware repository.

It reports, cheaply:

- repo root and dp version
- policy path
- Beads/doctor health
- instruction files
- adoption state
- campaign artifacts
- active or stale goal lease, when discoverable
- next safe actions
- relevant hints and expansion commands

Brief output is budgeted for agent context pressure. Use `--detail normal` or `--detail full` when
the brief response points to omitted detail.
