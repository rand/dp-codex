# SPEC-80.03 Codex-Operable Goal Emission

Status: active
Issue: dpcx-pb5.2
Parent: SPEC-80

[SPEC-80.03]

## Intent

dp must be able to turn a valid GoalContract into a Codex-operable `/goal` prompt without adding
new semantic judgment. Emission is formatting over a linted contract, not proof of readiness or
completion.

## Requirements

1. `dp goal emit <goal.json> --format codex --json` MUST require a valid GoalContract.
2. `dp agent prompt --goal <goal.json> --format codex --json` MUST use the same emission path.
3. The emitted prompt MUST include objective, evidence cues, read-first files, path boundaries,
   iteration policy, blocked-stop condition, start command, heartbeat command, complete/evidence
   command, block command, and release command.
4. The prompt MUST tell Codex to start through dp, run the smallest relevant check first, repair
   before broadening scope, route blockers through dp, and never claim completion without evidence.
5. Emission MUST NOT execute commands or validate evidence behavior.

## Verification

Required evidence for this slice:

```bash
dp goal emit tests/fixtures/goals/valid_spec_70_01.json --format codex --json
pytest tests/test_goal_emit.py
make check
```
