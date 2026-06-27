# Loop Ledger Schema

LoopLedger schema version `0.1` declares an operational graph of GoalContracts. It lets dp answer
which goal is ready next without relying on chat memory.

Required top-level fields:

1. `schema_version`: currently `0.1`.
2. `id`: stable loop id such as `LOOP-SPEC-80.04`.
3. `title`: non-empty human title.
4. `nodes`: non-empty list of loop nodes.

Required node fields:

1. `id`: unique node id.
2. `goal_id`: GoalContract id expected at `goal_path`.
3. `goal_path`: sane relative path to a valid GoalContract JSON file.
4. `depends_on`: list of node ids this node depends on.

Optional node fields:

1. `beads_issue_id`: Beads issue represented by the node.
2. `evidence_plan`: sane relative path to the node evidence plan.

Validation command:

```bash
dp loop lint <loop.json> --json
```

Status and next-goal commands:

```bash
dp loop status <loop.json> --json
dp loop next <loop.json> --claim --emit codex --json
```

When `--emit codex` is used, the next-goal package includes lifecycle commands plus
`evidence_run`, `complete`, `verify`, and `verify_fresh` commands. If the node or GoalContract
declares an EvidencePlan, those commands use `docs/evidence-runs/RUN-<goal-id>.json` as the concrete
run artifact path.

Exit codes:

1. `0`: valid lint, successful status, or next-goal package.
2. `1`: invalid loaded ledger, or no ready node for `next`.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, incomplete input,
   unsupported emit format, or invalid claim arguments.

Safety rules:

1. Loop lint never executes commands.
2. Loop commands never call an LLM.
3. Dependencies must resolve and be acyclic.
4. `next` skips blocked nodes and active non-stale claims.
5. Dependencies unlock only from verified goal state; evidence-pending is not treated as proof.
6. `next --claim` writes through the existing append-only goal event log.
