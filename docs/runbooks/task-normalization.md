# Task Status and Priority Normalization

`dp task` commands normalize status and priority inputs before delegating to Beads.

## Status Mapping

Canonical statuses passed to `bd`:

1. `open`
2. `in_progress`
3. `blocked`
4. `closed`
5. `deferred`

Accepted aliases:

1. `todo`, `to-do` -> `open`
2. `in-progress`, `inprogress`, `in progress` -> `in_progress`
3. `done` -> `closed`
4. `snoozed` -> `deferred`

Invalid status values fail fast with exit code `2` and guidance.

## Priority Mapping

Canonical priorities passed to `bd`:

1. `P0`
2. `P1`
3. `P2`
4. `P3`
5. `P4`

Accepted inputs:

1. `P0`-`P4`
2. `0`-`4` (mapped to `P0`-`P4`)

Invalid priority values fail fast with exit code `2` and guidance.

## Examples

```bash
dp task update dpcx-egm.3.3 --status in-progress --priority 1
# Delegates to: bd update dpcx-egm.3.3 --status in_progress --priority P1
```
