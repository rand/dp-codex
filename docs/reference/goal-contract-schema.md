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

## Intent Block

Optional below the intent-graph adoption level, required at it (marker
`docs/reference/intent-graph.md` plus the spec81 reference surface). A present intent block is
always validated in full. See `docs/specs/SPEC-83-intent-graph-substrate.md`.

```json
{
  "intent": {
    "authorship": "owner",
    "source": {"path": "docs/vision.md", "anchor": "doctor"},
    "verbatim": "Exact owner words this goal serves.",
    "parent": {
      "goal": "GOAL-ROOT",
      "contribution": "How this child serves the parent.",
      "residual": "What of the parent this child does not capture.",
      "parent_snapshot": "sha256:<64-hex>"
    },
    "defeaters": ["How the goal could fail while receipts stay green."],
    "outcome_contact": {
      "signal": "Real-world signal that settles the goal.",
      "channel": "docs/outcomes/doctor.md"
    }
  }
}
```

Rules:

1. `authorship` is one of `owner`, `agent_derived`, `owner_ratified`. It is a declaration;
   lint cannot machine-verify who authored the source document.
2. `source.path` must be an existing repo-relative file (not a directory, not the goal file
   itself). `verbatim` is not checked against the source content.
3. Root goals set `parent: null`. A root with `agent_derived` authorship lints clean as a
   proposed root, but `dp goal claim` and `dp goal start` refuse it (`unratified_root_goal`)
   until the owner sets authorship to `owner` or `owner_ratified`. Non-root parents name
   `goal` and `contribution`.
4. `parent.residual` and `defeaters` are audit-only when absent: omitting them (or setting
   them null) passes lint, and `dp graph audit` reports `missing_residual` /
   `missing_defeaters` warnings. A present residual must be a non-empty string; a present
   `defeaters` must be a non-empty list of non-empty strings.
5. `parent_snapshot` is optional; compute it with `goal_file_digest` in
   `dp.core.intent_graph` (sha256 over the parent goal file). `dp graph audit` flags malformed
   digests as `invalid_parent_snapshot` and mismatches as `stale_parent_snapshot`.
6. `outcome_contact` must bind `signal` and `channel`.

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
