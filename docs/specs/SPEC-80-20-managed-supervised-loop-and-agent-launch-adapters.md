# SPEC-80.20 Managed Supervised Loop And Agent Launch Adapters

Status: active
Issue: dpcx-pb5.17
Parent: SPEC-80

[SPEC-80.20]

## Intent

SPEC-80 now has contracts, state, evidence, loop selection, campaign recovery, readiness promotion,
and a one-step supervised handoff. The next increment is not a background autonomous runner. It is
a stronger supervised control-plane protocol:

1. A managed campaign-run mode that returns a stable stop reason for the next supervised action.
2. A goal-level agent launch adapter that claims and starts one GoalContract through dp, then emits
   the Codex prompt package.

Both commands remain explicit and opt-in. They do not launch Codex, call a model, execute evidence,
verify completion, or mutate Beads implicitly.

## Commands

```bash
dp campaign run <campaign.json> --driver codex --supervised --managed --json
dp campaign run <campaign.json> --driver codex --supervised --managed --max-steps 1 --json
dp agent launch --goal <goal.json> --driver codex --agent codex --lease 2h --supervised --json
```

`--max-steps` is bounded. In this slice, managed mode may claim at most one ready goal because the
agent still has to do the work between campaign steps.

## Requirements

1. Managed campaign run MUST require `--supervised`.
2. Managed campaign run MUST support only `--driver codex` in this slice.
3. Managed campaign run MUST refuse `state.status == draft` campaigns.
4. Managed campaign run MUST derive behavior from `dp campaign status` and the existing
   LoopLedger next-goal protocol.
5. Managed campaign run MUST stop before claiming when stale leases are present.
6. Managed campaign run MUST stop before claiming when the current resume action is
   `resume_claimed_goal`, `verify_evidence`, `resolve_blocker`, `campaign_verified`, or
   `no_ready_work`.
7. Managed campaign run MAY claim one ready goal when the current resume action is
   `claim_next_goal`.
8. Managed campaign run MUST append no more than one goal claim event per invocation.
9. Managed campaign run MUST append the same campaign handoff event as one-step run when it claims.
10. Managed campaign run MUST return `mode == managed_supervised`, `autonomous == false`, and
    `launched == false`.
11. Managed campaign run MUST return stable `stop_reason`, `iterations`, `next`, and
    `stop_conditions` fields.
12. `dp agent launch` MUST require `--supervised`.
13. `dp agent launch` MUST support only `--driver codex` in this slice.
14. `dp agent launch` MUST validate and emit the same Codex-operable GoalContract prompt as
    `dp agent prompt`.
15. `dp agent launch` MUST claim and start the goal through existing append-only goal state
    commands.
16. `dp agent launch` MUST not spawn Codex or any process.
17. `dp agent launch` MUST return lifecycle/evidence commands and `launched == false`.
18. Neither command may execute evidence, verify goals, call an LLM, mutate Beads, or run in hooks
    or CI as a blocking gate.

## Stop Reasons

| Condition | `stop_reason` | Exit code |
| --- | --- | --- |
| Draft campaign | `campaign_not_ready` | `1` |
| Stale lease present | `stale_lease` | `1` |
| Active claimed/started/pursuing goal | `active_claim` | `0` |
| Evidence pending | `evidence_pending` | `1` |
| Blocked goal | `blocked` | `1` |
| Ready goal claimed | `handoff_claimed` | `0` |
| Campaign verified | `campaign_verified` | `0` |
| No ready work | `no_ready_work` | `1` |
| Invalid max steps | `invalid_max_steps` | `2` |

## Formal Invariants

Let `C` be a CampaignManifest, `S(C)` the deterministic campaign status payload, and `N(C)` the
existing one-step next-goal protocol.

1. Bounded mutation:
   a managed campaign run appends at most one goal claim event and at most one campaign handoff
   event.
2. Stop before unsafe advance:
   if `S(C).resume.stale_claims != []`, managed run does not call `N(C)`.
3. Active work preservation:
   if `S(C).resume.action == resume_claimed_goal`, managed run returns that resume package and
   appends no claim event.
4. Evidence separation:
   if `S(C).resume.action == verify_evidence`, managed run does not execute or verify evidence.
5. Blocker separation:
   if `S(C).resume.action == resolve_blocker`, managed run does not create artifacts beyond what
   explicit blocker commands already do.
6. Launch purity:
   `agent launch` may append claim/start events, but `launched == false` and no external process is
   spawned.
7. Verification purity:
   neither managed run nor agent launch appends `verified` events.

## Non-Goals

1. No direct Codex subprocess execution.
2. No multi-goal background loop.
3. No automatic evidence execution.
4. No verification judgment.
5. No Beads synchronization side effect.
6. No model or network call.

## Verification

Required checks:

```bash
pytest tests/test_campaign_managed_run.py tests/test_agent_launch.py tests/test_campaign_run.py
pytest tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
