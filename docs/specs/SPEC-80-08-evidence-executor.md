# SPEC-80.08 Evidence Executor

Status: active
Issue: dpcx-pb5.8
Parent: SPEC-80

[SPEC-80.08]

## Intent

dp must be able to run evidence plans without becoming an arbitrary shell runner. The executor is
the first bridge from declarative evidence to recorded empirical output, so its safety boundary is
part of the product contract.

This slice implements `dp evidence run <evidence.json> --json` for already-lintable
EvidencePlan files. It does not decide goal completion, unlock loop dependencies, run campaigns, or
ask an LLM to judge behavior.

## Requirements

1. `dp evidence run <evidence.json> --json` MUST lint the plan before running any check.
2. If lint fails, the command MUST run no checks and return the lint result in stable JSON.
3. The executor MUST run commands with argv arrays and `shell=False`.
4. The executor MUST run only checks that pass deterministic EvidencePlan lint.
5. Each check MUST use its declared `timeout_seconds`.
6. Each check MUST run from a controlled cwd:
   1. Default cwd is the caller's current repository directory.
   2. Optional `cwd` is a sane relative path and must already exist.
7. Each check MUST run with a controlled environment allowlist; plan JSON MUST NOT provide
   arbitrary environment variables in this slice.
8. Each check MUST pass only when:
   1. The process exit code is in `success_exit_codes`.
   2. Every typed assertion passes.
9. Supported typed assertions MUST include:
   1. `exit_code_in`
   2. `stdout_json`
   3. `json_path_exists`
   4. `json_path_equals`
   5. `stdout_contains`
   6. `stderr_empty`
   7. `file_exists`
10. The command MUST emit stable JSON with `ok`, `command`, `evidence_id`, `goal_id`, `lint`,
    `checks`, `summary`, and optional `error`.
11. Exit codes MUST be:
    1. `0` when the plan is valid and every check passes.
    2. `1` when the plan is valid but a check fails, times out, or cannot run safely; also when a
       loaded plan is invalid.
    3. `2` for missing files, malformed JSON, non-object JSON, unsupported schemas, or incomplete
       evidence input.

## Formal Invariants

Let `P` be an EvidencePlan, `L(P)` its deterministic lint result, and `R(P)` the run result.

1. Lint gate: `L(P).exit_code != 0 => R(P).checks = []`.
2. No shell: for every executed check `c`, subprocess invocation uses
   `argv = c.argv` and `shell = False`.
3. Registered execution: every executed check has already satisfied the registered command prefix
   predicate from `dp evidence lint`.
4. Timeout bound: for every executed check `c`, runtime is bounded by `c.timeout_seconds` plus
   process cleanup overhead.
5. Deterministic success predicate: `R(P).ok` is the conjunction of all per-check exit-code and
   assertion predicates; no chat transcript, LLM judgment, or agent narration participates.
6. No hidden state: `R(P)` is computed from `P`, process outputs, declared cwd, and the controlled
   environment allowlist.

## Non-Goals

1. No raw shell or command string execution.
2. No command discovery from the host system.
3. No arbitrary environment injection.
4. No evidence-based transition from `evidence_pending` to `verified`.
5. No campaign, loop, or background agent runner.
6. No LLM-assisted evidence interpretation.

## Verification

Required evidence for this slice:

```bash
dp evidence run tests/fixtures/evidence/valid_run_goal_lint.json --json
pytest tests/test_evidence_run.py
make check
```
