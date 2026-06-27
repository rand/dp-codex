# Evidence Plan Schema

EvidencePlan schema version `0.1` declares checks that can prove or support a goal. The current
implementation lints plans only; it does not execute them.

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

Exit codes:

1. `0`: valid.
2. `1`: invalid plan.
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
2. Lint never calls an LLM.
3. Command checks use argv arrays only.
4. Shell control operators such as `&&`, `||`, pipes, redirects, semicolons, backticks, and
   substitutions are rejected in argv entries.
5. Commands must match registered prefixes.
6. Assertions must use known assertion types.
7. Mutating commands must not claim `read_only` mutation policy.
