# SPEC-80.04 Loop Ledgers

Status: active
Issue: dpcx-pb5.4
Parent: SPEC-80

[SPEC-80.04]

## Intent

dp must provide a deterministic loop ledger that turns a campaign graph into the next
agent-operable goal package. The ledger is an explicit repo artifact; it is not semantic campaign
planning, an evidence executor, or an autonomous runner.

## Requirements

1. `dp loop lint <loop.json> --json` MUST validate a LoopLedger without model calls, command
   execution, or hidden state.
2. `dp loop status <loop.json> --json` MUST reconstruct node readiness from the ledger, valid
   GoalContracts, and append-only goal events.
3. `dp loop next <loop.json> --claim --emit codex --json` MUST return the first ready unclaimed
   node in ledger order, claim its GoalContract through the existing goal event log, and include a
   complete Codex-operable package.
4. Loop JSON output MUST be stable and deterministic.
5. Exit codes MUST be:
   1. `0` for a valid lint, successful status, or next-goal package.
   2. `1` for a loaded but invalid ledger or no ready next goal.
   3. `2` for missing files, malformed JSON, non-object JSON, unsupported schemas, incomplete
      input, unsupported emit formats, or invalid claim arguments.
6. Loop nodes MUST reference valid GoalContract files by sane relative path.
7. Node ids and goal ids MUST be unique within a ledger.
8. Dependencies MUST resolve to node ids and MUST form an acyclic graph.
9. Blocked nodes MUST be skipped by `next`.
10. Claimed non-stale nodes MUST be skipped by `next`.
11. Dependencies MUST unlock only from verified goal state. `evidence_pending` is evidence
    recorded, not verified completion.
12. `next --emit codex` MUST include goal id, Beads issue id if present, Codex goal text,
    read-first files, evidence plan, allowed paths, and goal lifecycle commands.

## Non-Goals

1. No primary-spec semantic decomposition.
2. No LLM synthesis or judgment.
3. No evidence execution.
4. No autonomous or background agent runner.
5. No alternate hidden state store beyond repo artifacts and append-only goal events.

## Verification

Required evidence for this slice:

```bash
dp loop lint tests/fixtures/loops/valid_spec_80_04.json --json
pytest tests/test_loop_ledger.py
make check
```
