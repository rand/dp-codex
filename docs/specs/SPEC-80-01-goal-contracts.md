# SPEC-80.01 Goal Contracts

Status: active
Issue: dpcx-pb5.1
Parent: SPEC-80

[SPEC-80.01]

## Intent

dp must provide a typed, deterministic GoalContract boundary before any campaign compiler or
agent prompt generator can be trusted. A goal contract is the smallest durable object that tells
Codex what to do, what not to do, what evidence matters, and how blockers route into process
artifacts.

## Requirements

1. `dp goal lint <goal.json> --json` MUST validate a GoalContract without model calls, network
   calls, hidden state, or command execution.
2. Goal lint output MUST be stable JSON with `valid`, `goal_id`, `errors`, and `warnings`.
3. Exit codes MUST be:
   1. `0` for a valid contract.
   2. `1` for a syntactically loaded but invalid contract.
   3. `2` for missing files, malformed JSON, non-object JSON, unsupported schemas, or incomplete
      input that cannot be treated as a contract.
4. Goal contracts MUST declare schema version, id, title, level, objective, evidence, terminal
   states, and boundaries for nontrivial goals.
5. Goal evidence fields MAY name verification commands as declarative evidence cues, but lint MUST
   reject shell control operators and structured evidence `argv` fields that are not arrays.
6. Goal success MUST NOT depend on agent narration or self-report.
7. Campaign-level contracts MUST decompose into nodes instead of one giant objective.
8. Blocker routes MUST use known route types so future commands can create specs, ADRs, evidence
   stubs, or Beads follow-ups.

## Non-Goals

1. No LLM synthesis.
2. No evidence execution.
3. No loop scheduling.
4. No autonomous agent runner.

## Verification

Required evidence for this slice:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
pytest tests/test_goal_lint.py
make check
```
