# Agent Response Contract

Agent-facing dp commands use `dp.response.v1` when they are new SPEC-81 surfaces or when an
existing command is called with `--detail`.

Required fields:

1. `schema_version`: `dp.response.v1`.
2. `command`: the invoked dp command.
3. `status`: one of `ok`, `invalid`, `blocked`, `incomplete`, `warning`, or `error`.
4. `exit_code`: process exit code.
5. `summary`: one short sentence.
6. `result`: detail-mode dependent structured data.
7. `affordances`: phase, mutability, safety, freshness, idempotence, and cost.
8. `next_actions`: one to three concrete safe moves.
9. `hints`: stable hint codes with `dp explain` commands.
10. `artifacts`: references to files or event logs, not payload dumps.
11. `expansions`: commands for omitted detail.

Detail modes:

- `brief`: summary, affordances, key references, capped hints, and expansion handles.
- `normal`: brief plus the essential result needed for the next action.
- `full`: normal plus the underlying command payload.

Existing JSON consumers are preserved: legacy commands keep their original JSON unless `--detail`
is explicitly passed.
