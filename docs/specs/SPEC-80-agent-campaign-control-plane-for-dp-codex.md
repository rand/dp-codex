# SPEC-80: Agent Campaign Control Plane for dp-codex

Status: proposed
Audience: local Codex, future dp maintainers
Scope: principled upgrade to dp-codex so a comprehensive primary spec can be compiled into a disciplined, agent-operable campaign of specs, ADRs, validators, tests, Beads work, goals, evidence, and loops.

Implementation note, 2026-06-27: the foundation is implemented for GoalContract linting,
append-only goal lifecycle state, Codex prompt emission, deterministic EvidencePlan linting, and
controlled EvidencePlan execution. Evidence-run verification can now advance matching goals to
`verified`. LoopLedger lint/status/next-goal scheduling, CampaignManifest lint/status/recover, and
conservative primary-spec campaign scaffolding are also implemented. `dp campaign init` now records
deterministic semantic signals from the primary spec, including requirement, evidence, decision,
blocker, and dependency cues, while keeping generated campaigns in `draft`. `dp campaign refine`
can now deterministically materialize child spec/ADR stubs, GoalContract/EvidencePlan refinement
metadata, and explicit Beads work while preserving draft status. LLM-assisted refinement is now
agent-mediated: dp emits a request package for the calling agent provider and imports an explicit
response artifact only after deterministic validation. Supervised running remains planned
follow-up work.

## 1. Thesis

dp-codex should become the local campaign control plane for verified agentic development.

Not a generic agent framework.
Not a prompt-template library.
Not a Beads replacement.
Not a background autonomous runner first.

A campaign control plane means:

1. A comprehensive primary spec becomes a campaign.
2. The campaign becomes a dependency graph.
3. Graph nodes become goal contracts.
4. Goal contracts become Codex-operable `/goal` prompts.
5. Goals produce evidence.
6. Evidence advances campaign state.
7. Blockers become specs, ADRs, evidence plans, or Beads issues.
8. The next agent action is discoverable from artifacts, not memory or chat residue.

This keeps the division of labor clean:

* Codex is allowed to search, reason, edit, test, repair, and synthesize.
* dp constrains, records, validates, routes blockers, and defines what done means.
* Beads remains the task and dependency substrate.
* Specs, ADRs, evidence plans, goals, loops, and event logs become durable campaign memory.

## 2. User workflow to support

The target workflow starts from a rich primary spec.

Example shape:

1. User writes a comprehensive implementation-oriented primary spec.
2. User asks Codex to use dp to turn that spec into a disciplined process.
3. dp helps produce:

   * child specs
   * ADRs
   * validators
   * tests
   * Beads epics and issues
   * goal contracts
   * evidence plans
   * loop ledgers
   * Codex `/goal` prompts
   * campaign state and progress artifacts
4. Codex then asks dp for the next goal, executes it, records evidence, and advances or blocks the campaign.
5. A new Codex session can recover from repo artifacts and continue without reconstructing intent from chat history.

The desired operator experience should look like this eventually:

```bash
dp campaign init --primary-spec docs/primary/waveguide.md --write --json
dp campaign status CAMPAIGN-waveguide --json
dp loop next CAMPAIGN-waveguide --claim --emit codex --json
```

Codex receives a bounded `/goal` plus exact dp commands for start, progress, completion, and blocking.

After working:

```bash
dp goal complete GOAL-012 --evidence docs/evidence-runs/RUN-012.json --json
dp goal verify GOAL-012 --evidence docs/evidence-runs/RUN-012.json --json
dp loop next CAMPAIGN-waveguide --claim --emit codex --json
```

If blocked:

```bash
dp goal block GOAL-012 --reason needs_decision --write-artifact --json
```

The blocker should create the next disciplined artifact instead of ending as prose.

## 3. Design law

Preserve this law through every implementation choice:

```text
Primary spec becomes campaign.
Campaign becomes graph.
Graph nodes become goals.
Goals become agent contracts.
Contracts produce evidence.
Evidence advances state.
Blockers create artifacts.

Artifacts suggest context.
Evidence determines granularity.
Dependencies determine loop shape.
Generators may be stochastic.
Gates must be deterministic.
Verification determines done.
Campaign state must survive the agent session.
```

The decisive boundary:

```text
Authoring may use LLMs.
Blocking gates must not.
Hooks and CI must not.
Verification judgments must not.
```

LLMs may draft objectives, non-goals, rationale, decomposition hypotheses, and Codex prompt text. They may not be the blocking judge of validity, safety, evidence, or completion.

## 4. Current repo constraints and diagnosis

Before implementing, inspect the current repo and preserve its operating model.

Read at minimum:

```text
README.md
AGENTS.md
docs/concepts/disciplined-loop.md
docs/concepts/traceability-chain.md
docs/internals/command-runtime.md
docs/internals/data-contracts.md
docs/runbooks/decompose-workflow.md
docs/specs/SPEC-70-01-beads-doctor.md
dp/core/decompose.py
dp/core/verify.py
dp/cli/main.py
dp-policy.json
tests/
```

Local claims to verify before editing:

1. dp already has the right spine: Beads workflow, specs, traceability, ADRs, review, verify, policy, enforcement, progress, JSON command output, and explicit exit semantics.
2. `dp decompose` is currently context fitting, not semantic planning. It should not remain the conceptual basis for campaign decomposition.
3. `dp verify` is currently structural and provenance-oriented. It is not yet a behavioral evidence executor.
4. dp commands should continue to return stable JSON, explicit exit codes, and actionable errors.
5. Existing hooks and CI must remain fast and deterministic.
6. Any new agent or LLM capability must live in explicit authoring commands, not in hooks or blocking gates.

## 5. Non-goals

Do not do these:

1. Do not build a general agent framework.
2. Do not replace Beads.
3. Do not make raw generated JSON execute arbitrary shell.
4. Do not use LLM judgment as a blocking validator.
5. Do not make hooks or CI depend on network calls or model calls.
6. Do not implement a long-running autonomous campaign runner before contracts, state, and evidence are solid.
7. Do not confuse token-window fitting with semantic campaign planning.
8. Do not let “goal complete” mean “Codex says it is done.”
9. Do not introduce hidden state.
10. Do not implement this as prompt templates without typed contracts and state transitions.

## 6. Conceptual model

### 6.1 Campaign

A campaign is the durable execution object created from a primary spec.

It records:

* source primary spec
* source hash
* derived specs
* derived ADRs
* Beads epics and issues
* loop ledger
* goal contracts
* evidence plans
* dependencies
* state
* event log
* blockers
* next ready work

A campaign is not one giant goal. It is a graph of independently verifiable work.

### 6.2 Loop

A loop is the campaign’s operational graph.

It answers:

* What is ready?
* What is blocked?
* What is claimed?
* What has evidence?
* What can Codex do next?
* What should happen if a goal fails, blocks, or exhausts budget?

A loop is not necessarily an autonomous runner. At first it is a ledger and scheduler that an agent can operate through.

### 6.3 Goal

A goal is a scoped contract for one independently verifiable unit of work.

It includes:

* objective
* non-goals
* checkpoints
* evidence plan
* boundaries
* allowed commands
* iteration policy
* terminal states
* blocker routes
* provenance
* Codex `/goal` emission text

A goal is broad enough to permit discovery, but narrow enough to audit.

### 6.4 Evidence

Evidence is the external proof surface for a goal.

Evidence can include:

* tests
* lint
* typecheck
* build
* trace validation
* coverage
* `dp doctor --json`
* registered commands
* generated artifacts
* benchmark output
* structured reports

Evidence is not model belief.

### 6.5 Event log

Campaign and goal state transitions must be evented.

At first, use append-only JSONL under `.dp/`.

Example:

```text
.dp/campaigns/events.jsonl
.dp/goals/events.jsonl
```

This is intentionally simple. It gives recovery, auditability, leases, and status without building a database too early.

## 7. State machines

### 7.1 Goal states

Use explicit states.

```text
draft
linted
ready
claimed
started
pursuing
evidence_pending
verified
blocked
budget_exhausted
unsafe_scope
released
superseded
abandoned
```

### 7.2 Required transitions

Initial command surface:

```bash
dp goal lint <goal.json> --json
dp goal status <goal.json> --json
dp goal claim <goal.json> --agent codex --lease 2h --json
dp goal start <goal.json> --agent codex --json
dp goal heartbeat <goal.json> --json
dp goal report <goal.json> --status pursuing --note "..." --json
dp goal complete <goal.json> --evidence <path> --json
dp goal verify <goal.json> --evidence <path> --json
dp goal block <goal.json> --reason needs_decision --write-artifact --json
dp goal release <goal.json> --reason "context reset" --json
```

The first implementation may support a subset, but the data model must not preclude the full state machine.

### 7.3 Transition rules

Rules:

1. A goal cannot become `ready` unless `dp goal lint` passes.
2. A goal cannot become `verified` unless required evidence exists.
3. A goal cannot be claimed indefinitely. Claims require leases.
4. A stale lease must be recoverable by another session.
5. `budget_exhausted` is not success.
6. `blocked` must route to a next artifact where possible.
7. `unsafe_scope` must not be silently overridden.
8. `complete` must record evidence paths and evidence status.
9. Every state transition must append an event.

## 8. Data contracts

### 8.1 GoalContract

Suggested path:

```text
docs/goals/GOAL-<slug>.json
docs/goals/GOAL-<slug>.md
```

Suggested JSON shape:

```json
{
  "schema_version": "0.1",
  "id": "GOAL-SPEC-70.01",
  "title": "Make SPEC-70.01 true",
  "source": {
    "kind": "spec",
    "id": "SPEC-70.01",
    "path": "docs/specs/SPEC-70-01-beads-doctor.md",
    "input_hash": "sha256:..."
  },
  "level": "goal",
  "objective": "Concrete, evidence-checkable end state.",
  "non_goals": [
    "Explicitly excluded work."
  ],
  "checkpoints": [
    {
      "id": "SPEC-70.01-R1",
      "description": "A requirement-level checkpoint.",
      "source_ref": "SPEC-70.01"
    }
  ],
  "evidence": {
    "evidence_plan": "docs/evidence/EVIDENCE-SPEC-70.01.json",
    "verification_commands": [
      "dp goal lint docs/goals/GOAL-SPEC-70.01.json --json",
      "dp evidence lint docs/evidence/EVIDENCE-SPEC-70.01.json --json",
      "make check"
    ],
    "trace_ids": [
      "SPEC-70.01"
    ]
  },
  "boundaries": {
    "read_first": [
      "docs/specs/SPEC-70-01-beads-doctor.md",
      "dp/core/verify.py",
      "dp/cli/main.py"
    ],
    "preferred_paths": [
      "dp/core",
      "dp/cli",
      "tests",
      "docs"
    ],
    "allowed_paths": [
      "dp",
      "tests",
      "docs",
      "AGENTS.md",
      "README.md",
      "pyproject.toml"
    ],
    "forbidden_paths": [],
    "allowed_commands": [
      "make test",
      "make lint",
      "make typecheck",
      "make check",
      "dp doctor --json"
    ]
  },
  "iteration_policy": {
    "mode": "smallest_relevant_check_first",
    "max_attempts": 5,
    "after_each_attempt": [
      "record changed files",
      "run the smallest relevant failing check",
      "repair failures before broadening scope",
      "run broader checks only after local checks pass"
    ]
  },
  "terminal_states": {
    "success": "All required evidence passes.",
    "blocked": "Required context, fixture, command, validator, or decision is missing.",
    "budget_exhausted": "Iteration budget is exhausted without satisfying evidence.",
    "unsafe_scope": "Required changes exceed declared boundaries."
  },
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
    },
    "unsafe_scope": {
      "action": "create_scope_decision",
      "also_create_beads_issue": true
    }
  },
  "outputs": {
    "codex_goal": "/goal ..."
  },
  "provenance": {
    "generated_by": {
      "kind": "human|agent|llm|deterministic_scaffold",
      "model": null,
      "provider": null,
      "prompt_hash": null,
      "input_artifact_hashes": {},
      "linter_version": "0.1",
      "reviewed": false
    }
  }
}
```

### 8.2 GoalLintReport

`dp goal lint --json` should emit:

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
  "warnings": [
    {
      "code": "broad_boundary",
      "path": "$.boundaries.allowed_paths",
      "message": "Allowed paths are broad relative to evidence paths."
    }
  ]
}
```

Exit semantics:

```text
0 = valid
1 = invalid contract
2 = malformed input, missing file, unsupported schema, or incomplete input
```

### 8.3 EvidencePlan

Suggested path:

```text
docs/evidence/EVIDENCE-<slug>.json
```

Suggested JSON shape:

```json
{
  "schema_version": "0.1",
  "id": "EVIDENCE-SPEC-70.01",
  "goal_id": "GOAL-SPEC-70.01",
  "checks": [
    {
      "id": "doctor-json",
      "kind": "registered_command",
      "argv": ["dp", "doctor", "--json"],
      "timeout_seconds": 30,
      "success_exit_codes": [0, 2],
      "assertions": [
        {"type": "stdout_json"},
        {"type": "json_path_exists", "path": "$.checks"}
      ]
    }
  ]
}
```

Rules:

1. No raw shell strings.
2. Use argv arrays.
3. Use a registry or allowlist.
4. Every check must have timeout semantics.
5. Every check must have explicit success exit codes.
6. Assertions must be typed.
7. Mutation-sensitive checks must declare mutation policy.
8. Evidence lint may validate without executing.

### 8.4 LoopLedger

Suggested path:

```text
docs/loops/LOOP-<slug>.json
```

Suggested JSON shape:

```json
{
  "schema_version": "0.1",
  "id": "LOOP-primary-spec-001",
  "title": "Campaign derived from primary spec",
  "source": {
    "kind": "primary_spec",
    "path": "docs/primary/waveguide.md",
    "input_hash": "sha256:..."
  },
  "scheduler": "beads",
  "context_policy": "fresh_context_per_goal",
  "nodes": [
    {
      "id": "node-001",
      "kind": "goal",
      "goal_id": "GOAL-...",
      "beads_issue_id": "...",
      "depends_on": [],
      "status": "pending",
      "evidence_plan": "docs/evidence/EVIDENCE-....json"
    }
  ],
  "stop_rules": [
    "stop on missing required decision",
    "stop on missing evidence surface",
    "stop on unsafe scope expansion",
    "stop when budget is exhausted without evidence"
  ]
}
```

### 8.5 CampaignManifest

Suggested path:

```text
docs/campaigns/CAMPAIGN-<slug>.json
```

Suggested shape:

```json
{
  "schema_version": "0.1",
  "id": "CAMPAIGN-waveguide",
  "title": "Waveguide implementation campaign",
  "primary_spec": {
    "path": "docs/primary/waveguide.md",
    "input_hash": "sha256:..."
  },
  "artifacts": {
    "specs": [],
    "adrs": [],
    "goals": [],
    "evidence_plans": [],
    "loops": [],
    "beads_epics": [],
    "beads_issues": []
  },
  "state": {
    "status": "draft|ready|active|blocked|verified|abandoned",
    "current_loop": "LOOP-waveguide",
    "current_goal": null
  }
}
```

## 9. Command surface

### 9.1 Campaign commands

Target:

```bash
dp campaign init --primary-spec <path-or-url> --write --json
dp campaign refine <campaign.json> --write --json
dp campaign refine <campaign.json> --write --create-beads --json
dp campaign refine <campaign.json> --llm --json
dp campaign refine <campaign.json> --llm-response <response.json> --write --json
dp campaign lint <campaign.json> --json
dp campaign status <campaign.json> --json
dp campaign recover <campaign.json> --json
```

### 9.2 Loop commands

Target:

```bash
dp loop lint <loop.json> --json
dp loop status <loop.json> --json
dp loop next <loop.json> --claim --emit codex --json
dp loop record <loop.json> --goal <goal-id> --status <status> --evidence <path> --json
```

`dp loop next` is the agent handoff command. It should return everything Codex needs to run the next goal.

Example output:

```json
{
  "campaign_id": "CAMPAIGN-waveguide",
  "loop_id": "LOOP-waveguide",
  "goal_id": "GOAL-012",
  "beads_issue_id": "bd-a3f8.2",
  "lease": {
    "holder": "codex",
    "expires_at": "..."
  },
  "codex_goal": "/goal ...",
  "read_first": [
    "docs/specs/SPEC-012.md",
    "docs/adrs/ADR-003.md"
  ],
  "evidence_plan": "docs/evidence/EVIDENCE-012.json",
  "allowed_paths": [
    "dp",
    "tests",
    "docs"
  ],
  "commands": {
    "start": "dp goal start docs/goals/GOAL-012.json --agent codex --json",
    "heartbeat": "dp goal heartbeat docs/goals/GOAL-012.json --json",
    "complete": "dp goal complete docs/goals/GOAL-012.json --evidence <run.json> --json",
    "verify": "dp goal verify docs/goals/GOAL-012.json --evidence <run.json> --json",
    "block": "dp goal block docs/goals/GOAL-012.json --reason <reason> --write-artifact --json",
    "release": "dp goal release docs/goals/GOAL-012.json --reason <reason> --json"
  }
}
```

### 9.3 Goal commands

Target:

```bash
dp goal lint <goal.json> --json
dp goal emit <goal.json> --format codex --json
dp goal status <goal.json> --json
dp goal claim <goal.json> --agent codex --lease 2h --json
dp goal start <goal.json> --agent codex --json
dp goal heartbeat <goal.json> --json
dp goal report <goal.json> --status pursuing --note "..." --json
dp goal complete <goal.json> --evidence <path> --json
dp goal verify <goal.json> --evidence <path> --json
dp goal block <goal.json> --reason needs_decision --write-artifact --json
dp goal release <goal.json> --reason "context reset" --json
```

### 9.4 Evidence commands

Target:

```bash
dp evidence lint <evidence.json> --json
dp evidence run <evidence.json> --json
```

Evidence execution is valid only behind deterministic lint, registered argv commands, declared
timeouts, controlled cwd/env, and typed assertion semantics.

### 9.5 Agent commands

Target:

```bash
dp agent prompt --goal <goal.json> --format codex --json
dp agent launch --goal <goal.json> --driver codex
dp campaign run <campaign.json> --driver codex --supervised
```

Do not implement `launch` or `campaign run` first. The control plane must work manually before it runs agents.

## 10. Codex `/goal` emission

`dp goal emit --format codex` should produce a goal with this shape:

```text
/goal <objective>, verified by <specific evidence>, while preserving <constraints>. Use <allowed files, tools, and boundaries>. Between iterations, <iteration policy>. If blocked, budget-exhausted, or no safe path remains, <report blocker and route to artifact>.
```

The emitted goal should also instruct Codex to use dp’s state commands.

Example:

```text
/goal Make SPEC-70.01 true: dp-codex must tolerate current Beads CLI behavior by providing a read-only `dp doctor --json` health path, distinguishing missing `bd`, missing `.beads`, and unusable initialized databases, avoiding removed `bd sync` assumptions, and ensuring pre-push safeguards check provider health without mutation. Verify with the linked evidence plan, targeted doctor/provider tests, `dp doctor --json`, trace validation for SPEC-70.01, and `make check`, while preserving deterministic exit semantics and current Beads-compatible command guidance. Prefer changes under `dp/providers`, `dp/cli`, `dp/enforcement`, `tests`, and relevant docs. Start by running `dp goal start ...`. Between iterations, run the smallest relevant failing check first and repair before broadening scope. If Beads command behavior, fixture setup, or provider semantics are ambiguous, run `dp goal block ... --reason needs_decision --write-artifact` instead of guessing. Record evidence with `dp goal complete ... --evidence <run.json>` and advance only with `dp goal verify ... --evidence <run.json>` after evidence passes.
```

## 11. LLM policy

Implement this architecture even if the first slices do not call an LLM.

Allowed LLM-assisted authoring commands:

```text
dp campaign init --llm
dp campaign refine
dp goal synthesize
dp goal refine
dp agent prompt
```

Forbidden LLM use:

```text
dp goal lint
dp evidence lint
dp loop lint
dp campaign lint
dp evidence run assertions
dp verify completion judgment
hooks
CI
```

Preferred synthesis loop:

```text
deterministic scaffold extraction
LLM drafts semantic fields
dp goal lint
structured lint failures feed refinement
repeat within budget
write only if lint passes, or write draft as invalid with reasons
```

Record provenance for generated artifacts:

```json
{
  "kind": "llm",
  "provider": "calling_agent",
  "provider_source": "calling_agent",
  "model": "unknown-or-actual-model-id",
  "network_calls": true,
  "prompt_hash": "sha256:...",
  "prompt_template": "campaign-refine-calling-agent-v0.1",
  "input_artifact_hashes": {
    "primary_spec": "sha256:..."
  },
  "output_hash": "sha256:...",
  "dp_version": "unknown-or-version",
  "linter_version": "0.1",
  "created_at": "UTC timestamp",
  "reviewed": false
}
```

For local Codex-driven workflows, the most appropriate LLM provider is the provider currently in use
by the agent calling dp, usually Codex using a native OpenAI model. Network/model calls are expected
only in explicit authoring flows such as `dp campaign refine --llm`; in the agent-mediated protocol,
dp emits the request and imports the response artifact while the calling agent performs the model
call. Blocking gates, hooks, CI, evidence assertions, and verification judgments remain LLM-free.

## 12. Blocker routing

A blocker must produce the next disciplined-process artifact.

Rules:

```text
needs_specification:
    create or propose spec stub
    create Beads follow-up

needs_decision:
    create or propose ADR stub through dp adr
    create Beads follow-up

needs_validator:
    create or propose evidence plan stub
    create Beads follow-up

unsafe_scope:
    create or propose scope decision/spec issue

budget_exhausted:
    record progress
    release or requeue goal
    create smallest useful follow-up
```

Do not terminate into inert prose when the repo has mechanisms for specs, ADRs, tasks, and evidence.

## 13. Primary-spec campaign compiler

The eventual command:

```bash
dp campaign init --primary-spec <path-or-url> --write --json
```

It should compile a comprehensive spec into:

1. Campaign manifest
2. Loop ledger
3. Child specs
4. ADR stubs
5. Evidence plan stubs
6. Goal contracts
7. Beads epics/issues
8. Dependency edges
9. Codex-operable next goal

The compiler should extract or synthesize:

* major objectives
* non-goals
* requirements
* risks
* architectural decisions
* unresolved questions
* validators needed
* implementation slices
* evidence surfaces
* dependencies
* campaign milestones

Conservative behavior:

* If the primary spec is too ambiguous, emit `needs_specification`.
* If a decision blocks decomposition, emit `needs_decision`.
* If no validator can be named, emit `needs_validator`.
* If a slice is too broad, split into campaign nodes.
* If artifact generation requires judgment, use authoring-mode LLM and then deterministic gates.

## 14. Implementation milestones

### M0: Repo-native planning artifacts

Before code, create or update repo-native design artifacts.

Suggested specs:

```text
docs/specs/SPEC-80-01-goal-contracts.md
docs/specs/SPEC-80-02-goal-state-machine.md
docs/specs/SPEC-80-03-loop-ledgers.md
docs/specs/SPEC-80-04-evidence-plans.md
docs/specs/SPEC-80-05-campaign-control-plane.md
docs/specs/SPEC-80-06-primary-spec-campaign-compiler.md
```

Suggested ADRs:

```text
Generation Under Deterministic Gates
Goal State Is Append-Only Events
Evidence Plans Use Registered Checks, Not Raw Shell
Decompose Becomes Context Fitting, Not Semantic Planning
dp Is a Campaign Control Plane, Not an Agent Runner
```

Use existing dp and Beads surfaces where possible.

### M1: GoalContract schema and linter

Implement first.

Commands:

```bash
dp goal lint <goal.json> --json
```

Likely files:

```text
dp/core/goal_contract.py
dp/core/goal_lint.py
dp/cli/main.py
tests/test_goal_lint.py
tests/fixtures/goals/valid_spec_70_01.json
tests/fixtures/goals/invalid_*.json
docs/reference/goal-contract-schema.md
```

Validation rules:

* JSON object required
* supported schema version
* non-empty id
* non-empty title
* valid level
* non-empty objective
* objective must not be vague without measurable evidence
* evidence reference or verification commands required
* success terminal state required
* blocked terminal state required
* nontrivial goals require boundaries
* raw shell strings prohibited in structured evidence
* evidence plan paths must be relative and sane
* trace IDs must look valid where present
* success cannot depend on agent self-report
* campaign-level goals must decompose into nodes
* blocker routes must be known route types

Acceptance:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
pytest tests/test_goal_lint.py
make check
```

### M2: Goal event log and state machine

Implement:

```bash
dp goal status <goal.json> --json
dp goal claim <goal.json> --agent codex --lease 2h --json
dp goal start <goal.json> --agent codex --json
dp goal heartbeat <goal.json> --json
dp goal complete <goal.json> --evidence <path> --json
dp goal verify <goal.json> --evidence <path> --json
dp goal block <goal.json> --reason needs_decision --json
dp goal release <goal.json> --reason <reason> --json
```

Use append-only JSONL events.

Likely files:

```text
dp/core/goal_state.py
dp/core/events.py
tests/test_goal_state.py
docs/reference/goal-state-machine.md
```

Acceptance:

* claiming writes event
* stale lease can be detected
* start requires valid or linted goal
* complete requires evidence path
* block records reason
* release records reason
* state can be reconstructed from events

### M3: Loop ledger lint, status, and next

Implement:

```bash
dp loop lint <loop.json> --json
dp loop status <loop.json> --json
dp loop next <loop.json> --claim --emit codex --json
```

Rules:

* nodes form acyclic graph
* dependencies resolve
* next returns ready unclaimed node
* claim writes goal event
* `--emit codex` includes goal text and state commands
* blocked nodes surface blocker routes
* no autonomous runner

Likely files:

```text
dp/core/loop_ledger.py
dp/core/loop_status.py
tests/test_loop_ledger.py
docs/reference/loop-ledger-schema.md
```

### M4: Codex goal emission

Implement:

```bash
dp goal emit <goal.json> --format codex --json
dp agent prompt --goal <goal.json> --format codex --json
```

Acceptance:

* emitted text includes objective, evidence, constraints, boundaries, iteration policy, blocked-stop condition
* emitted text includes dp start, complete, block, and release commands
* missing evidence prevents emission or emits invalid status

### M5: EvidencePlan schema and linter

Implement:

```bash
dp evidence lint <evidence.json> --json
```

Rules:

* no raw shell
* argv arrays only
* command registry or allowlist
* timeouts required
* success exit codes explicit
* typed assertions only
* mutation policy declared where relevant

Do not execute yet.

### M6: Campaign manifest and status

Implement:

```bash
dp campaign lint <campaign.json> --json
dp campaign status <campaign.json> --json
dp campaign recover <campaign.json> --json
```

This makes campaign state visible and recoverable before primary-spec generation exists.

### M7: Primary-spec campaign scaffold

Implement conservative scaffold mode:

```bash
dp campaign init --primary-spec <path> --write --json
```

Initial mode may be deterministic and incomplete:

* hash primary spec
* create campaign shell
* identify major sections
* create draft loop ledger
* create draft goals or placeholders
* create `needs_refinement` markers where semantic decomposition is needed

Implemented follow-up in SPEC-80.11:

```bash
dp campaign refine <campaign.json> --write --json
dp campaign refine <campaign.json> --write --create-beads --json
```

Deterministic refinement writes child spec/ADR stubs, records GoalContract/EvidencePlan refinement
metadata, and can explicitly materialize Beads work. It preserves `draft` campaign state and does
not call an LLM or execute evidence.

Implemented follow-up in SPEC-80.12:

```bash
dp campaign refine <campaign.json> --llm --json
dp campaign refine <campaign.json> --llm-response <response.json> --write --json
```

LLM-assisted refinement is agent-mediated. dp emits a prompt-bound request for the provider/model
already in use by the calling agent, then imports a response artifact only after deterministic
validation of campaign id, prompt hash, provider provenance, known goal ids, safe paths, and
argv-only evidence proposals without raw shell syntax. Imported model content remains draft
authoring metadata.

### M8: Evidence execution

Implemented in SPEC-80.08 after evidence lint stabilized:

```bash
dp evidence run <evidence.json> --json
```

Rules:

* no `shell=True`
* argv only
* allowlisted commands
* timeout required
* cwd controlled
* env controlled
* stdout/stderr captured
* assertion results typed
* mutation policy respected

This is security-sensitive. Treat it as a real executor.

### M9: Goal verification integration

Implemented in SPEC-80.10 for manual evidence-run verification:

```bash
dp goal verify <goal.json> --evidence <run.json> --json
```

The command checks:

```text
goal lint
evidence run output shape
goal id match
evidence plan path match
current evidence plan lint
current evidence plan sha256 match
```

Do not use hand-authored truth booleans as behavioral proof of goal completion.

### M10: Supervised campaign runner

Only after manual protocol works:

```bash
dp campaign run <campaign.json> --driver codex --supervised
```

This should be a thin adapter over the same commands Codex can call manually. The protocol comes first, the runner comes last.

## 15. Acceptance criteria

### First mergeable slice

Complete when:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
pytest tests/test_goal_lint.py
make check
```

and:

* `dp goal lint` exists
* stable JSON output exists
* exit semantics match dp conventions
* golden valid fixture passes
* invalid fixtures fail with structured errors
* docs explain GoalContract
* no synthesis, model calls, loop runner, or evidence executor has been smuggled in

### First useful agent-operable slice

Complete when:

```bash
dp goal lint tests/fixtures/goals/valid_spec_70_01.json --json
dp goal claim tests/fixtures/goals/valid_spec_70_01.json --agent codex --json
dp goal start tests/fixtures/goals/valid_spec_70_01.json --agent codex --json
dp goal emit tests/fixtures/goals/valid_spec_70_01.json --format codex --json
dp goal block tests/fixtures/goals/valid_spec_70_01.json --reason needs_decision --json
pytest
make check
```

and:

* goal state can be reconstructed from event log
* Codex prompt includes dp lifecycle commands
* blocked states are recorded and routeable
* leases prevent invisible duplicate claims

### Campaign-control slice

Complete when:

```bash
dp loop next docs/loops/<loop>.json --claim --emit codex --json
```

returns a complete Codex-operable package:

* goal id
* Beads issue id if present
* codex goal text
* read-first files
* evidence plan
* allowed paths
* start command
* complete command
* block command
* release command
* lease information

### Broader project acceptance

Complete when dp can support:

```bash
dp campaign init --primary-spec <PRIMARY_SPEC_PATH> --write --json
dp campaign status docs/campaigns/<campaign>.json --json
dp loop next docs/loops/<loop>.json --claim --emit codex --json
dp goal start docs/goals/<goal>.json --agent codex --json
dp goal complete docs/goals/<goal>.json --evidence <run.json> --json
dp goal verify docs/goals/<goal>.json --evidence <run.json> --json
```

and a new Codex session can recover campaign state from repo artifacts without chat memory.

## 16. Development discipline

Use dp to improve dp.

Process:

1. Run `dp doctor --json`.
2. Inspect Beads state.
3. Create or claim the implementation issue.
4. Add specs/ADRs for the design.
5. Implement one slice at a time.
6. Add tests in the same change.
7. Keep diffs scoped.
8. Run the smallest relevant checks first.
9. Run `make check` before completion.
10. Update docs.
11. Record blockers as artifacts, not prose.
12. Do not claim full campaign control until the command surface actually works.

## 17. Final instruction

Build the control plane, not the fireworks.

The first thing to make real is not the LLM compiler, not an autonomous runner, and not a beautiful dashboard.

The first thing to make real is a typed, deterministic, linted GoalContract with state transitions Codex can operate.

Once that exists, every later feature has back-pressure:

* bad goal text fails lint
* unsafe evidence fails lint
* stale claims recover
* blockers become artifacts
* Codex can ask for the next goal
* completion requires evidence

That is the inflection point where dp stops being a disciplined checklist and becomes the operating system for verified agent campaigns.
