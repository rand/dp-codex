# SPEC-81.01 Executable Agent Usability Evals

Status: implemented

## Objective

Strengthen `dp agent eval --json` from static category reporting into a compact,
fixture-backed transcript harness for the SPEC-81 Agent Experience layer.

The harness must prove that agent-facing guidance is not only present, but
actionable against representative local repositories under context pressure.

## Contract

`dp agent eval --json` must emit schema `dp.agent_eval.v1` with:

- `results`: one row per required eval category.
- `transcripts`: compact fixture-backed command transcripts.
- `metrics.fixture_backed_categories`: count of categories backed by local fixtures.
- `metrics.transcript_step_count`: count of transcript steps.
- `golden_transcript`: the canonical high-level handoff flow.

Each transcript step must include:

- `command`: the command an agent should run.
- `ok`: whether the observed result matched the expectation.
- `exit_code`: the expected command exit code or simulated command outcome.
- `summary`: one sentence about the observed behavior.

Failure-oriented transcript steps must include stable repair evidence such as
`observed_error_code`, `hints`, or `next_actions`.

## Fixture Requirements

The eval must use local fixture repositories under `tests/fixtures/spec81_projects/`
for these categories:

- bootstrap-first-command
- instruction-preservation
- legacy-project-adoption
- skill-triggering
- hook-audit-correctness
- token-budget-compliance
- no-ready-loop-handling

Fixture-backed checks may call deterministic core functions directly. They must
not call LLMs, the network, or hidden mutating commands against the real
repository.

## Non-Goals

- Do not turn this into a live model eval.
- Do not run Codex hooks or skills as CI requirements.
- Do not use `dp agent eval` as a replacement for deterministic gates.
- Do not dump full command payloads by default.

## Token Discipline

The default JSON payload should stay compact enough for agent bootstrap and
handoff use. Transcript steps should summarize observed behavior and expose
expansion routes instead of embedding full diagnostics.

## Acceptance

1. Tests assert the transcript schema and fixture-backed categories before
   implementation.
2. `dp agent eval --json` reports fixture-backed transcript steps and compact
   metrics.
3. No-ready loop handling is represented by an expected deterministic failure
   with hint routing.
4. `pytest tests/test_agent_usability_evals.py`, `dp agent eval --json`, and
   `make check` pass.
