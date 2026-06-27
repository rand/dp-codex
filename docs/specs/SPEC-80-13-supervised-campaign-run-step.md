# SPEC-80.13 Supervised Campaign Run Step

Status: active
Issue: dpcx-pb5.9.4
Parent: SPEC-80

[SPEC-80.13]

## Intent

The manual SPEC-80 protocol is now real: campaigns can be scaffolded and refined, loops can select
ready work, goals can be claimed and started, Codex prompts can be emitted, evidence can run under
registered argv checks, and verified goal state can be reconstructed from append-only events.

The first runner must not skip over that protocol. It should be a supervised one-step adapter that
lets an operator or Codex session ask dp to prepare the next executable handoff from a CampaignManifest.

This slice implements:

```bash
dp campaign run <campaign.json> --driver codex --supervised --json
```

The command validates the campaign, resolves the current loop, claims one next ready goal, emits a
Codex handoff package, and stops. It does not launch Codex, run evidence, verify completion, or loop
in the background.

## Requirements

1. The command MUST require `--supervised`.
2. The only supported driver in this slice is `codex`.
3. The command MUST validate the CampaignManifest before resolving work.
4. The command MUST resolve `state.current_loop` to one declared loop artifact.
5. The command MUST use the existing LoopLedger next-goal protocol with claim semantics.
6. The command MUST claim at most one ready goal per invocation.
7. The command MUST emit the same Codex-operable package available through `dp loop next --claim
   --emit codex`.
8. The command MUST return explicit lifecycle commands for start, heartbeat, complete, verify,
   block, and release.
9. The command MUST report stop conditions that tell the caller to stop after one handoff, stop on
   no ready work, stop on blockers, stop on unsafe scope, and never claim completion without
   evidence.
10. The command MUST NOT launch Codex or any other agent process.
11. The command MUST NOT execute evidence.
12. The command MUST NOT verify goals or advance campaign state to verified.
13. Unsupported drivers, missing `--supervised`, invalid campaigns, and no-ready-work outcomes MUST
   produce stable JSON and explicit exit codes.

## Output Shape

Successful output:

```json
{
  "ok": true,
  "command": "campaign.run",
  "mode": "supervised_once",
  "driver": "codex",
  "campaign_id": "CAMPAIGN-example",
  "supervised": true,
  "autonomous": false,
  "launched": false,
  "status": {},
  "next": {},
  "stop_conditions": [],
  "message": "Supervised campaign step prepared."
}
```

The `next` object is the `dp loop next --claim --emit codex` package.

## Formal Invariants

Let `C` be a valid CampaignManifest, `L` its current LoopLedger, and `R(C)` a successful supervised
run result.

1. Single-step:
   `R(C)` selects at most one loop node.
2. Protocol preservation:
   `R(C).next.command == "loop.next"`.
3. Claim event:
   when a ready goal exists, exactly one goal claim event is appended by the underlying goal state
   protocol.
4. No launch:
   `R(C).launched == false` and no external agent process is spawned.
5. No evidence:
   `R(C)` does not execute EvidencePlan checks.
6. No verification:
   `R(C)` does not append `verified` events.
7. Driver scope:
   unsupported drivers fail with exit code `2`.

## Non-Goals

1. No background runner.
2. No direct Codex process launch.
3. No multi-goal loop.
4. No model calls.
5. No evidence execution or verification judgment.

## Verification

Required evidence:

```bash
pytest tests/test_campaign_run.py tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
