# Agent Bootstrap

`dp agent bootstrap --json --detail brief` is the canonical first command for agents in a
dp-aware repository.

It reports, cheaply:

- repo root and dp version
- policy path
- Beads/doctor health
- instruction files
- adoption state
- derived active and blocked campaign artifacts (verified/draft history and invalid sidecars are
  excluded from routing, except an otherwise-verified campaign with current `not_useful` outcome
  contact remains active for corrective routing; full detail reports historical artifacts)
- active or stale goal lease, when discoverable
- the active goal's exact owner intent as the first brief result, before workflow actions
- next safe actions
- relevant hints and expansion commands

When a goal lease exists, bootstrap emits one goal-specific next action instead of repeating
generic orientation work. Stale leases and their intent are labeled stale and route only to
release; they are never described as active.

Brief output is budgeted for agent context pressure. Exact owner intent takes precedence over the
size target: concise intent remains within the normal budget, while unusually long verbatim intent
may exceed it rather than being silently truncated. Use `--detail normal` or `--detail full` when
the brief response points to omitted detail.
