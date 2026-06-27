# SPEC-80.05 Evidence Plans

Status: active
Issue: dpcx-pb5.5
Parent: SPEC-80

[SPEC-80.05]

## Intent

dp must validate evidence plans before any command can treat them as proof. An EvidencePlan is a
typed, deterministic declaration of checks that may later be executed by a controlled evidence
runner. This slice only lints plans; it does not execute anything.

## Requirements

1. `dp evidence lint <evidence.json> --json` MUST validate an EvidencePlan without command
   execution, model calls, network calls, or hidden state.
2. Evidence lint output MUST be stable JSON with `valid`, `evidence_id`, `goal_id`, `errors`, and
   `warnings`.
3. Exit codes MUST be:
   1. `0` for a valid plan.
   2. `1` for a syntactically loaded but invalid plan.
   3. `2` for missing files, malformed JSON, non-object JSON, unsupported schemas, or incomplete
      input that cannot be treated as an evidence plan.
4. Evidence plans MUST declare schema version, id, goal id, and at least one check.
5. Each check MUST declare a unique id, kind, argv array, timeout, success exit codes, typed
   assertions, and mutation policy.
6. The first implementation MUST support `registered_command` checks only.
7. Registered command checks MUST use known command prefixes rather than arbitrary executables.
8. Raw shell strings and shell control operators MUST be rejected.
9. Optional file paths and cwd values MUST be sane relative paths.
10. Mutating checks MUST declare an explicit non-read-only mutation policy.

## Non-Goals

1. No evidence execution.
2. No shell execution.
3. No dynamic command discovery.
4. No LLM judgment.
5. No completion verification integration.

## Verification

Required evidence for this slice:

```bash
dp evidence lint tests/fixtures/evidence/valid_spec_80_05.json --json
pytest tests/test_evidence_lint.py
make check
```
