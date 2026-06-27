# Evidence Plan Schema

EvidencePlan schema version `0.1` declares checks that can prove or support a goal. The current
implementation can lint plans and run them through the controlled evidence executor.

Required top-level fields:

1. `schema_version`: currently `0.1`.
2. `id`: non-empty stable evidence id such as `EVIDENCE-SPEC-80.05`.
3. `goal_id`: non-empty goal id such as `GOAL-SPEC-80.05`.
4. `checks`: non-empty list of check objects.

Required check fields:

1. `id`: unique non-empty check id.
2. `kind`: currently `registered_command`.
3. `argv`: non-empty array of strings.
4. `timeout_seconds`: positive integer timeout.
5. `success_exit_codes`: non-empty list of integer exit codes from `0` through `255`.
6. `assertions`: non-empty list of typed assertion objects.
7. `mutation_policy`: one of `read_only`, `writes_workspace`, or `writes_event_log`.

Validation command:

```bash
dp evidence lint <evidence.json> --json
```

Execution command:

```bash
dp evidence run <evidence.json> --json
```

`dp evidence run` emits the run report to stdout. Persist that JSON as a repo artifact when it will
be used by `dp goal complete` or `dp goal verify`.

Lint exit codes:

1. `0`: valid.
2. `1`: invalid plan.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete input.

Run exit codes:

1. `0`: valid plan and every check passed.
2. `1`: loaded plan is invalid, or at least one valid check failed, timed out, or could not run
   safely.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete input.

JSON output:

```json
{
  "valid": false,
  "evidence_id": "EVIDENCE-SPEC-80.05",
  "goal_id": "GOAL-SPEC-80.05",
  "errors": [
    {
      "code": "missing_timeout",
      "path": "$.checks[0].timeout_seconds",
      "message": "Evidence check must define timeout_seconds."
    }
  ],
  "warnings": []
}
```

Safety rules:

1. Lint never executes checks.
2. Run executes checks only after lint succeeds.
3. Lint and run never call an LLM.
4. Command checks use argv arrays only.
5. Shell control operators such as `&&`, `||`, pipes, redirects, semicolons, backticks, and
   substitutions are rejected in argv entries.
6. Commands must match registered prefixes.
7. Run invokes subprocesses with `shell=False`.
8. Run uses declared timeouts, an existing sane relative cwd, and a controlled environment allowlist.
9. Assertions must use known assertion types.
10. Mutating commands must not claim `read_only` mutation policy.

Run JSON output:

```json
{
  "ok": true,
  "command": "evidence.run",
  "evidence_id": "EVIDENCE-SPEC-80.08-RUN",
  "goal_id": "GOAL-SPEC-80.08",
  "evidence_plan": {
    "path": "tests/fixtures/evidence/valid_run_goal_lint.json",
    "sha256": "sha256:..."
  },
  "lint": {
    "valid": true,
    "evidence_id": "EVIDENCE-SPEC-80.08-RUN",
    "goal_id": "GOAL-SPEC-80.08",
    "errors": [],
    "warnings": []
  },
  "checks": [
    {
      "id": "goal-lint-valid",
      "ok": true,
      "status": "passed",
      "argv": ["dp", "goal", "lint", "tests/fixtures/goals/valid_spec_70_01.json", "--json"],
      "cwd": ".",
      "timeout_seconds": 30,
      "exit_code": 0,
      "stdout": "{\"errors\": [], \"goal_id\": \"GOAL-SPEC-70.01\", \"valid\": true, \"warnings\": []}\n",
      "stderr": "",
      "assertions": [
        {
          "type": "exit_code_in",
          "path": "$.checks[0].assertions[0]",
          "ok": true,
          "message": "Exit code 0 in [0]."
        }
      ],
      "error": null
    }
  ],
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0,
    "timed_out": 0,
    "errored": 0
  },
  "error": null
}
```
