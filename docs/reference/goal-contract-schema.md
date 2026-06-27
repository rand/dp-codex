# Goal Contract Schema

GoalContract schema version `0.1` is a deterministic contract for one campaign goal or node.

Required top-level fields:

1. `schema_version`: currently `0.1`.
2. `id`: non-empty stable goal id such as `GOAL-SPEC-70.01`.
3. `title`: non-empty human title.
4. `level`: one of `campaign`, `goal`, `node`, or `milestone`.
5. `objective`: concrete objective; vague objectives require measurable evidence.
6. `evidence`: at least one `evidence_plan`, `verification_commands`, or `checks` entry.
7. `terminal_states.success`: evidence-backed success state.
8. `terminal_states.blocked`: blocker state.
9. `boundaries`: required for campaign, goal, and node levels.

Optional blocker routing:

```json
{
  "blocked_routes": {
    "needs_specification": {
      "action": "create_spec_stub",
      "also_create_beads_issue": true
    },
    "needs_decision": {
      "action": "create_adr_stub",
      "also_create_beads_issue": true
    },
    "needs_validator": {
      "action": "create_evidence_stub",
      "also_create_beads_issue": true
    }
  }
}
```

`dp goal block --write-artifact` currently materializes `create_spec_stub`, `create_adr_stub`, and
`create_evidence_stub`. Unsupported or missing routes still record the blocked event and return
stable JSON explaining the route failure.

Validation command:

```bash
dp goal lint <goal.json> --json
```

Exit codes:

1. `0`: valid.
2. `1`: invalid contract.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete input.

JSON output:

```json
{
  "valid": false,
  "goal_id": "GOAL-SPEC-70.01",
  "errors": [
    {
      "code": "missing_blocked_terminal",
      "path": "$.terminal_states.blocked",
      "message": "Goal must define a blocked terminal state."
    }
  ],
  "warnings": []
}
```

Safety rules:

1. Lint never calls an LLM.
2. Lint never executes evidence commands.
3. Structured evidence `argv` fields must be arrays.
4. Shell control operators such as `&&`, `||`, pipes, redirects, semicolons, backticks, and
   substitutions are rejected in evidence strings.
5. Evidence plan and boundary paths must be sane relative paths.
6. Success states cannot rely on agent self-report or narration.
7. Blocker routing is deterministic and does not call an LLM.
