# SPEC-81: Agent Experience Layer for dp-codex

Status: implemented
Depends on: SPEC-80 Agent Campaign Control Plane
Audience: local Codex, dp maintainers, adopting-project maintainers
Scope: make dp-codex highly effective, efficient, recoverable, and respectful for coding agents operating inside real repositories.

Implementation note, 2026-06-28: SPEC-81 is implemented as an additive Agent Experience layer over
the SPEC-80 campaign-control foundation. New protocol primitives define `dp.response.v1`,
ToolCards, and stable hint explanations. `dp agent bootstrap`, `dp agent capabilities`,
`dp explain`, instruction governance, adoption/migration inspect-plan-apply-verify, repo-scoped
skills, hook governance, and deterministic agent evals are implemented. Existing high-leverage
commands keep legacy JSON by default and expose response envelopes only through explicit
`--detail` modes. Adoption plans are additive, AGENTS.md files are preserved, hooks remain local and
LLM-free, and token budgets are enforced by tests.

Follow-up note, 2026-06-28: SPEC-81.01 strengthens `dp agent eval --json` with executable
fixture-backed transcripts for bootstrap, instruction preservation, legacy adoption, hook audit,
skill triggering, token budgets, and no-ready loop handling.

## 1. Thesis

SPEC-80 made dp a durable campaign-control plane.

SPEC-81 makes dp legible to agents.

The goal is not nicer CLI output. The goal is an Agent Experience layer: a protocol and interaction surface that lets coding agents discover the local workflow, understand command safety, choose the next correct move, use compact context, respect existing project instructions, recover old dp projects, and route failure into durable artifacts.

A normal CLI answers:

```text
What data did this command return?
```

An agent experience layer answers:

```text
What happened?
What does it mean?
What is safe to do next?
What changed?
What state must be preserved?
What detail was omitted, and how do I fetch it?
What local instructions override the generic workflow?
```

dp should become the local control plane that makes agents better without becoming the agent.

## 2. Relationship to SPEC-80

SPEC-80 defines the campaign control plane:

```text
Primary spec becomes campaign.
Campaign becomes graph.
Graph nodes become goals.
Goals become agent contracts.
Contracts produce evidence.
Evidence advances state.
Blockers create artifacts.
Campaign state survives the agent session.
```

SPEC-81 defines the agent experience layer over that control plane:

```text
Commands advertise affordances.
Affordances guide agent action.
Hints route repair.
Instructions preserve local law.
Skills teach narrow workflows.
Hooks steer but do not decide.
Migration heals old projects.
Budgets protect context.
Evals prove the interface works.
```

SPEC-81 must not reimplement campaigns, goals, evidence, or loops. It should make the existing SPEC-80 system easier for agents to use correctly, cheaply, and safely.

## 3. Design law

Preserve this law:

```text
Agent-facing commands are protocol surfaces, not text dumps.

Every high-leverage command should expose:
- semantic status
- typed result
- next safe actions
- stable hint codes
- artifact references
- expansion handles
- safety and mutability metadata
- freshness and state information

Existing project instructions are local law.
Migration must inspect and plan before applying.
Hooks may steer, but gates decide.
Skills should teach workflows, not duplicate manuals.
Token efficiency is a correctness property.
```

The core boundary remains:

```text
Authoring may be stochastic.
Blocking gates must be deterministic.
Verification determines done.
Campaign state must survive the session.
```

## 4. Agent journey map

Design dp around the actual journey of an agent in a repository.

### 4.1 Orient

The agent needs to know:

* where it is
* whether dp is installed and healthy
* which instructions apply
* whether this is a new, current, old, or partially migrated dp project
* whether there is active campaign state
* what command should be run next

Primary command:

```bash
dp agent bootstrap --json --detail brief
```

### 4.2 Discover protocol

The agent needs to know what dp commands are available and how to call them safely.

Primary command:

```bash
dp agent capabilities --json
```

### 4.3 Respect instructions

The agent needs to discover local guidance before acting.

Primary commands:

```bash
dp instructions inspect --json
dp instructions audit --json
dp instructions plan-update --json
```

### 4.4 Adopt or migrate

The agent needs to get a project into a healthy dp state without overwriting local history.

Primary commands:

```bash
dp adopt inspect --json
dp adopt plan --write --json
dp adopt apply <plan.json> --json
dp adopt verify --json
```

`dp migrate ...` may remain as an alias or compatibility surface for old dp projects, but the conceptual verb should be adoption: a project may be new to dp, old dp, partially migrated, or already current.

### 4.5 Claim and work

The agent needs to get one bounded unit of work.

Primary commands:

```bash
dp loop next <loop.json> --claim --emit codex --json --detail normal
dp goal start <goal.json> --agent codex --json
```

### 4.6 Repair

The agent needs small, actionable failure information.

Primary commands:

```bash
dp evidence run <evidence.json> --json --detail normal
dp explain <hint-or-error-code> --json
```

### 4.7 Block

The agent needs to turn missing decisions, specs, or validators into artifacts.

Primary command:

```bash
dp goal block <goal.json> --reason needs_decision --write-artifact --json
```

### 4.8 Handoff and recover

The agent needs to end, compact, resume, or hand off cleanly.

Primary commands:

```bash
dp agent handoff --json --detail brief
dp campaign recover <campaign.json> --json
dp agent bootstrap --json --detail brief
```

## 5. Non-goals

Do not do these:

1. Do not replace existing AGENTS.md files automatically.
2. Do not create AGENTS.override.md automatically.
3. Do not flatten local project instructions into dp defaults.
4. Do not treat hooks as complete enforcement boundaries.
5. Do not make hooks call LLMs.
6. Do not make CI depend on Codex hooks, skills, or model calls.
7. Do not dump full campaign, goal, evidence, or diagnostic payloads by default.
8. Do not hide repair detail behind vague success or failure summaries.
9. Do not require a flag-day migration for old dp projects.
10. Do not create one giant dp skill.
11. Do not make skills contradict AGENTS.md.
12. Do not treat agent usability as cosmetic formatting.

## 6. Agent-facing response envelope

### 6.1 Purpose

All new agent-facing commands, and eventually all high-leverage existing commands, should support a shared response envelope.

The envelope must be compact by default and expandable on demand.

### 6.2 Schema

```json
{
  "schema_version": "dp.response.v1",
  "command": "dp loop next",
  "status": "ok",
  "exit_code": 0,
  "summary": "Claimed GOAL-012. Start it, read 2 files, then run the linked evidence plan.",
  "result": {},
  "affordances": {
    "phase": "claim",
    "mutability": "writes_state",
    "idempotent": false,
    "safety": "bounded_repo_state_change",
    "freshness": "current",
    "cost": {
      "latency": "low",
      "tokens": "low",
      "executes_commands": false
    }
  },
  "next_actions": [
    {
      "id": "start_goal",
      "label": "Start the claimed goal",
      "command": "dp goal start docs/goals/GOAL-012.json --agent codex --json",
      "why": "Records that Codex began active work."
    }
  ],
  "hints": [
    {
      "code": "DP-HINT-LOOP-CLAIMED",
      "severity": "info",
      "message": "A lease is active. Heartbeat or release before switching goals.",
      "explain_command": "dp explain DP-HINT-LOOP-CLAIMED --json"
    }
  ],
  "artifacts": [
    {
      "kind": "goal",
      "path": "docs/goals/GOAL-012.json",
      "id": "GOAL-012"
    }
  ],
  "expansions": [
    {
      "id": "full_goal",
      "command": "dp inspect goal docs/goals/GOAL-012.json --json --detail full"
    }
  ]
}
```

### 6.3 Required fields

For agent-facing commands:

```text
schema_version
command
status
exit_code
summary
result
affordances
next_actions
hints
artifacts
expansions
```

### 6.4 Status values

Use a small set:

```text
ok
invalid
blocked
incomplete
warning
error
```

### 6.5 Agent phases

Every agent-facing response should identify a phase:

```text
orient
discover
adopt
migrate
claim
start
work
repair
verify
block
release
handoff
recover
```

### 6.6 Mutability values

Every agent-facing command should classify its side effects:

```text
read_only
writes_dp_state
writes_project_artifacts
runs_registered_checks
may_modify_repo
may_contact_network
destructive
```

### 6.7 Cost values

Every agent-facing command should classify cost:

```text
latency: low | medium | high
tokens: low | medium | high
executes_commands: true | false
network: true | false
```

This lets the agent choose cheap orientation commands before expensive detail commands.

## 7. ToolCards and capability discovery

### 7.1 Purpose

`dp agent capabilities` should not just list commands. It should expose ToolCards: compact command descriptors that agents can use like a local tool manifest.

This makes the CLI MCP-ready even before dp exposes an MCP server.

### 7.2 Command

```bash
dp agent capabilities --json
```

### 7.3 ToolCard schema

```json
{
  "schema_version": "dp.capabilities.v1",
  "toolcards": [
    {
      "name": "dp loop next",
      "purpose": "Return the next ready goal and optional Codex handoff.",
      "phase": "claim",
      "input_shape": "LoopLedger path plus claim/emission flags.",
      "output_schema": "dp.response.v1",
      "mutability": "writes_dp_state",
      "idempotent": false,
      "destructive": false,
      "open_world": false,
      "requires_trust": false,
      "cost": {
        "latency": "low",
        "tokens": "medium",
        "executes_commands": false
      },
      "common_next": [
        "dp goal start",
        "dp goal block",
        "dp goal release"
      ],
      "detail_modes": [
        "brief",
        "normal",
        "full"
      ]
    }
  ],
  "schemas": {
    "response": "dp.response.v1",
    "goal": "GoalContract/0.1",
    "evidence": "EvidencePlan/0.1",
    "loop": "LoopLedger/0.1",
    "campaign": "CampaignManifest/0.1"
  }
}
```

### 7.4 Safety annotations

Each ToolCard should eventually expose:

```text
read_only
idempotent
destructive
open_world
requires_approval
writes_paths
reads_paths
runs_commands
```

These annotations should be truthful. They are not enforcement by themselves; they are affordances for agents and future adapters.

## 8. Progressive disclosure

### 8.1 Output modes

High-leverage agent-facing commands should support:

```bash
--detail brief
--detail normal
--detail full
```

Semantics:

```text
brief  = summary, status, one to three next actions, key artifacts, expansion handles
normal = brief + essential result + capped hints
full   = normal + full diagnostics and uncapped validation detail
```

### 8.2 Field selection

Where practical:

```bash
--fields status,summary,next_actions,result.goal_id
```

Field selection is not required in the first slice, but the response envelope should not preclude it.

### 8.3 Expansion handles

If a response omits detail because of budget, it must include expansion handles.

Example:

```json
{
  "omitted": {
    "reason": "detail_budget",
    "count": 14,
    "expand_command": "dp evidence run docs/evidence/EVIDENCE-foo.json --json --detail full"
  }
}
```

Never truncate blindly when a structured omission is possible.

## 9. Hints and explanations

### 9.1 Hint codes

Hints should be stable, sparse, and expandable.

Initial registry:

```text
DP-HINT-BOOTSTRAP-RUN-DOCTOR
DP-HINT-INSTRUCTIONS-FOUND
DP-HINT-INSTRUCTIONS-CONFLICT
DP-HINT-INSTRUCTIONS-TOO-LARGE
DP-HINT-ADOPTION-AVAILABLE
DP-HINT-ADOPTION-PLAN-REQUIRED
DP-HINT-MIGRATION-LEGACY-ARTIFACTS
DP-HINT-GOAL-NOT-STARTED
DP-HINT-GOAL-LEASE-STALE
DP-HINT-EVIDENCE-MISSING
DP-HINT-EVIDENCE-RUN-STALE
DP-HINT-EVIDENCE-FAILED
DP-HINT-CAMPAIGN-DRAFT
DP-HINT-LOOP-NO-READY-NODES
DP-HINT-BLOCKER-NEEDS-ADR
DP-HINT-BLOCKER-NEEDS-SPEC
DP-HINT-BLOCKER-NEEDS-VALIDATOR
DP-HINT-HOOKS-UNTRUSTED
DP-HINT-HOOK-BYPASSED
DP-HINT-SKILL-SUGGESTED
DP-HINT-SKILL-TRIGGER-AMBIGUOUS
DP-HINT-TOKEN-BUDGET-TRUNCATED
```

### 9.2 Explain command

Add:

```bash
dp explain <hint-or-error-code> --json
dp explain <hint-or-error-code> --format markdown
```

Example:

```json
{
  "schema_version": "dp.explain.v1",
  "code": "DP-HINT-EVIDENCE-MISSING",
  "severity": "error",
  "summary": "The goal references an evidence plan that does not exist.",
  "why_it_matters": "The goal cannot be verified without external evidence.",
  "next_actions": [
    {
      "command": "dp goal block docs/goals/GOAL-012.json --reason needs_validator --write-artifact --json",
      "why": "Route the missing validator into a durable artifact."
    }
  ],
  "docs": [
    "docs/reference/evidence-plan-schema.md"
  ]
}
```

### 9.3 Error quality rule

Every blocking error should include:

```text
stable code
short summary
why it matters
smallest next action
artifact route if applicable
expansion command for full detail
```

## 10. Agent bootstrap

### 10.1 Command

```bash
dp agent bootstrap --json --detail brief
dp agent bootstrap --json --detail normal
dp agent bootstrap --json --detail full
```

### 10.2 Purpose

`bootstrap` is the canonical first command for an agent in a dp-enabled repo.

It should cheaply answer:

* where am I?
* is dp healthy?
* what instructions apply?
* is this repo adopted, current, legacy, or unknown?
* are campaigns present?
* is a goal claimed or stale?
* what should I do next?
* what skills are relevant?
* what detail did dp omit?

### 10.3 Example output

```json
{
  "schema_version": "dp.response.v1",
  "command": "dp agent bootstrap",
  "status": "ok",
  "exit_code": 0,
  "summary": "dp is available. One active campaign found. No claimed goal.",
  "result": {
    "repo": {
      "root": ".",
      "dp_version": "0.1",
      "policy_path": "dp-policy.json"
    },
    "instructions": {
      "files": [
        "AGENTS.md"
      ],
      "status": "ok",
      "audit_command": "dp instructions audit --json"
    },
    "campaigns": {
      "active": [
        "docs/campaigns/CAMPAIGN-my-project.json"
      ]
    },
    "adoption": {
      "state": "current",
      "inspect_command": "dp adopt inspect --json"
    }
  },
  "affordances": {
    "phase": "orient",
    "mutability": "read_only",
    "idempotent": true,
    "safety": "safe_orientation",
    "freshness": "current",
    "cost": {
      "latency": "low",
      "tokens": "low",
      "executes_commands": false
    }
  },
  "next_actions": [
    {
      "id": "claim_next_goal",
      "command": "dp loop next docs/loops/LOOP-my-project.json --claim --emit codex --json",
      "why": "Claim the next ready campaign goal."
    }
  ],
  "hints": [],
  "artifacts": [],
  "expansions": [
    {
      "id": "full_bootstrap",
      "command": "dp agent bootstrap --json --detail full"
    }
  ]
}
```

## 11. Instruction governance

### 11.1 Principle

Existing project instructions are local law.

dp may inspect, audit, summarize, and propose updates. It must not silently override or rewrite instruction files.

### 11.2 Commands

```bash
dp instructions inspect --json
dp instructions audit --json
dp instructions plan-update --json
dp instructions apply-update <plan.json> --json
```

### 11.3 Files to discover

At minimum:

```text
AGENTS.md
AGENTS.override.md
nested AGENTS.md files
nested AGENTS.override.md files
configured fallback instruction files when discoverable
README.md
CONTRIBUTING.md
dp-policy.json
.codex/config.toml
.codex/hooks.json
.agents/skills/
```

### 11.4 Inspect output

`inspect` should preserve precedence.

Example:

```json
{
  "schema_version": "dp.instructions.inspect.v1",
  "status": "ok",
  "files": [
    {
      "path": "AGENTS.md",
      "kind": "agents",
      "scope": "repo",
      "size_bytes": 4200,
      "summary": "Repository workflow, tests, session completion, push requirements.",
      "contains_dp_guidance": true,
      "precedence": 10
    },
    {
      "path": "services/api/AGENTS.md",
      "kind": "agents",
      "scope": "nested",
      "size_bytes": 1300,
      "summary": "API service-specific testing and migration rules.",
      "contains_dp_guidance": false,
      "precedence": 20
    }
  ],
  "next_actions": [
    {
      "command": "dp instructions audit --json",
      "why": "Check for conflicts and missing dp agent bootstrap guidance."
    }
  ]
}
```

### 11.5 Audit checks

Audit for:

```text
missing dp bootstrap guidance
conflicting test commands
conflicting session completion rules
unsafe push or bypass guidance
duplicate dp instructions
oversized instruction files
nested override risks
stale old-dp command names
missing adoption/migration notes
skills that contradict AGENTS.md
hooks that contradict AGENTS.md
```

### 11.6 Plan update behavior

`plan-update` should create a reviewable plan, not mutate by default.

Prefer:

1. Minimal patch to existing AGENTS.md.
2. A short dp section, not a rewrite.
3. Links to docs and skills instead of inlining long guidance.
4. Preservation of stricter existing project rules.
5. Human review for conflicts.
6. No AGENTS.override.md unless explicitly requested.

Suggested section:

```markdown
## dp Agent Workflow

- Start with `dp agent bootstrap --json --detail brief`.
- For campaign work, use `dp loop next ... --claim --emit codex --json`.
- Start, block, release, and complete goals through dp lifecycle commands.
- Respect this file and any nested AGENTS.md files before dp hints.
- Treat dp hints as workflow affordances, not permission to ignore project-specific instructions.
- Do not mark work complete without evidence.
```

## 12. Adoption and migration

### 12.1 Principle

Adoption should heal projects without erasing their history.

Use a staged flow:

```text
inspect -> plan -> apply -> verify
```

not:

```text
detect -> mutate
```

### 12.2 Commands

Prefer the conceptual namespace:

```bash
dp adopt inspect --json
dp adopt plan --write --json
dp adopt apply <adoption-plan.json> --json
dp adopt verify --json
dp adopt status --json
```

Compatibility aliases may exist:

```bash
dp migrate inspect --json
dp migrate plan --write --json
dp migrate apply <migration-plan.json> --json
dp migrate verify --json
```

### 12.3 Inspect modes

`dp adopt inspect` should classify the repo:

```text
not_adopted
legacy_dp
partial_spec80
current_spec80
current_spec81
unknown
```

### 12.4 Inspect should detect

```text
dp-policy.json version
old goal schema
old evidence schema
old loop/campaign artifacts
legacy verify manifests
legacy decompose outputs
missing docs directories
old command names in docs
old Beads provider assumptions
missing .dp event directories
existing hooks
existing AGENTS.md files
skills absent or stale
Codex hooks absent or stale
campaign artifacts absent
instruction conflicts
```

### 12.5 Plan output

Write:

```text
docs/migrations/MIGRATION-<date>-<slug>.json
docs/migrations/MIGRATION-<date>-<slug>.md
```

Plan shape:

```json
{
  "schema_version": "dp.adoption_plan.v1",
  "id": "MIGRATION-2026-06-27-agent-experience",
  "status": "planned",
  "source_state": {
    "classification": "legacy_dp",
    "has_agents_md": true,
    "has_campaigns": false,
    "has_legacy_verify": true
  },
  "changes": [
    {
      "id": "add-agent-bootstrap-guidance",
      "kind": "patch",
      "path": "AGENTS.md",
      "mode": "propose",
      "reason": "Add minimal dp bootstrap guidance without replacing existing instructions."
    },
    {
      "id": "create-event-dir",
      "kind": "mkdir",
      "path": ".dp/goals",
      "mode": "apply",
      "reason": "Enable append-only goal lifecycle events."
    }
  ],
  "conflicts": [
    {
      "code": "DP-MIGRATE-CONFLICT-SESSION-COMPLETION",
      "path": "AGENTS.md",
      "summary": "Existing session completion rules are stricter than dp defaults. Preserve existing rules."
    }
  ],
  "verification": [
    "dp instructions audit --json",
    "dp agent bootstrap --json --detail brief",
    "dp doctor --json"
  ]
}
```

### 12.6 Apply rules

`apply` must:

* default to dry-run unless explicitly applying a plan
* never overwrite AGENTS.md without a patch preview
* create reversible patch records where practical
* stop on conflicts unless explicitly allowed
* write adoption events
* preserve legacy artifacts unless migration is explicit
* create Beads follow-ups for unresolved decisions where task surfaces exist

### 12.7 Verify rules

`verify` should check:

```text
dp doctor returns healthy or actionable incomplete state
instructions inspect/audit succeeds
agent bootstrap succeeds
policy version is known
campaign artifacts validate if present
legacy artifacts are migrated or recorded
hooks are auditable
skills are valid if present
```

## 13. Skills

### 13.1 Principle

Skills should be small workflow capsules.

They should teach the agent when and how to use dp, not duplicate dp’s entire manual.

### 13.2 Commands

```bash
dp skills scaffold --target repo --json
dp skills lint --json
dp skills audit --json
dp skills eval --json
```

### 13.3 Skill placement

For Codex, repo-scoped skills should live under:

```text
.agents/skills/
```

Do not assume every adopting repo wants them installed. Scaffold only with explicit write/apply.

### 13.4 Skill design rules

Each skill must:

* have one job
* include a short trigger-rich description
* define when to use it
* define when not to use it
* name the first dp command to run
* preserve local AGENTS.md precedence
* keep the main SKILL.md compact
* put detail in `references/`
* avoid scripts unless deterministic behavior or external tooling is needed

### 13.5 Initial skills

```text
dp-agent-bootstrap
dp-campaign-control
dp-goal-lifecycle
dp-evidence-repair
dp-adoption-migration
dp-instruction-governance
dp-session-handoff
dp-hook-triage
```

### 13.6 Skill trigger evals

`dp skills eval` should include prompt fixtures:

```text
"I just opened this repo, what should I do first?"
"Use the next campaign goal."
"Evidence failed, repair it."
"Upgrade this old dp project."
"Do not overwrite our AGENTS.md."
"Hook failed."
"End this session cleanly."
```

Each fixture should assert the expected skill or no-skill result.

## 14. Hook governance

### 14.1 Principle

Hooks are steering and local automation. They are not the source of truth.

### 14.2 Hook taxonomy

dp must distinguish:

```text
Git hooks
Codex hooks
Claude hooks
CI checks
dp policy gates
evidence checks
```

### 14.3 Commands

```bash
dp hooks audit --json
dp hooks doctor --json
dp hooks scaffold --target git --json
dp hooks scaffold --target codex --json
dp hooks explain <hook-id> --json
```

### 14.4 Git hooks

Git hooks may enforce deterministic local rules.

They must be:

* local
* deterministic
* fast
* LLM-free
* network-free unless explicitly configured
* auditable
* bypassable only through explicit audited paths

### 14.5 Codex hooks

Codex hooks may:

* remind the agent to bootstrap
* suggest relevant skills
* block narrow deterministic hazards
* compactly summarize dp status
* warn when a goal lease is active
* filter noisy command output

Codex hooks must not:

* replace dp validation
* make completion judgments
* call LLMs
* mutate campaign state unless explicitly configured
* assume every tool path is interceptable
* emit large context by default

### 14.6 Suggested Codex hook templates

Provide templates, not automatic installation:

```text
SessionStart:
  suggest `dp agent bootstrap --json --detail brief`

UserPromptSubmit:
  suggest relevant dp skill for campaign/goal/evidence/adoption prompts

PreToolUse:
  block narrow destructive commands and obvious boundary violations

PostToolUse:
  summarize failed dp command hints compactly

PreCompact:
  ask agent to capture dp campaign/goal status

PostCompact:
  remind agent to re-bootstrap

Stop:
  suggest session handoff checks
```

### 14.7 Hook audit checks

Audit for:

```text
untrusted project hooks
changed hook hashes
hooks that call network
hooks that call LLMs
hooks that mutate files
hooks that duplicate dp gates
hooks that emit excessive output
hooks that contradict AGENTS.md
hooks that rely on unsupported host features
hooks without timeout
hooks with relative paths that break from subdirectories
```

## 15. Token efficiency and context budgets

### 15.1 Principle

Token efficiency is a correctness property for agent tools.

Bloated output increases agent error rate by crowding out task context.

### 15.2 Budgets

Initial budgets:

```text
dp agent bootstrap --detail brief <= 2,000 chars
dp agent capabilities <= 5,000 chars
dp instructions inspect --detail brief <= 3,000 chars
dp adopt inspect --detail brief <= 3,000 chars
dp goal status --detail brief <= 1,500 chars
dp campaign status --detail brief <= 2,500 chars
dp loop next --claim --emit codex --detail normal <= 7,000 chars
common blocking error <= 2,500 chars
common evidence failure <= 4,000 chars
```

Budgets may be adjusted with evidence, but they must exist.

### 15.3 Snapshot tests

Add tests that verify:

* required fields exist
* summary is short
* next actions are capped
* hints are capped
* artifacts are references, not dumps
* expansions are present for omitted detail
* full detail remains available
* brief mode contains the next safe move
* output remains under budget

## 16. Agent usability evals

### 16.1 Principle

Do not rely on taste. Test agent experience.

### 16.2 Evals to add

Add a lightweight local eval suite:

```bash
dp agent eval --json
```

or test-only fixtures if a command is premature.

Eval categories:

```text
bootstrap-first-command
next-action-quality
error-repair-routing
instruction-preservation
legacy-project-adoption
skill-triggering
hook-audit-correctness
token-budget-compliance
resume-after-compaction
no-ready-loop-handling
```

### 16.3 Metrics

Track:

```text
time_to_first_correct_command
invalid_command_rate
missing_next_action_rate
hint_explain_coverage
over_budget_response_count
instruction_conflict_detection_rate
migration_plan_non_destructive_rate
skill_trigger_precision
skill_trigger_recall
hook_false_block_rate
recovery_success_rate
```

These can start as deterministic fixture metrics, not live model evals.

### 16.4 Golden transcripts

Add golden transcript fixtures that simulate an agent session:

1. Open repo.
2. Bootstrap.
3. Discover instructions.
4. Claim next goal.
5. Encounter evidence failure.
6. Explain hint.
7. Block or repair.
8. Handoff.

The expected transcript should be short, deterministic, and inspectable.

## 17. Implementation sequence

### M1: Agent response envelope and ToolCards

Likely files:

```text
dp/core/agent_response.py
dp/core/toolcards.py
dp/core/hints.py
tests/test_agent_response.py
tests/test_toolcards.py
docs/reference/agent-response-contract.md
docs/reference/toolcards.md
docs/reference/hint-codes.md
```

Acceptance:

```bash
pytest tests/test_agent_response.py
pytest tests/test_toolcards.py
make check
```

### M2: Agent bootstrap and capabilities

Commands:

```bash
dp agent bootstrap --json --detail brief
dp agent bootstrap --json --detail normal
dp agent bootstrap --json --detail full
dp agent capabilities --json
```

Acceptance:

```bash
dp agent bootstrap --json --detail brief
dp agent capabilities --json
pytest tests/test_agent_bootstrap.py
make check
```

### M3: Explain command and hint registry

Command:

```bash
dp explain <hint-or-error-code> --json
```

Acceptance:

```bash
dp explain DP-HINT-EVIDENCE-MISSING --json
pytest tests/test_hints.py
make check
```

### M4: Instruction governance

Commands:

```bash
dp instructions inspect --json
dp instructions audit --json
dp instructions plan-update --json
```

Fixtures:

```text
repo_with_no_agents
repo_with_root_agents
repo_with_nested_agents
repo_with_agents_override
repo_with_strict_session_completion
repo_with_old_dp_guidance
repo_with_conflicting_skills
repo_with_conflicting_hooks
```

Acceptance:

```bash
pytest tests/test_instructions.py
make check
```

### M5: Adoption and migration inspect/plan

Commands:

```bash
dp adopt inspect --json
dp adopt plan --write --json
```

Compatibility aliases:

```bash
dp migrate inspect --json
dp migrate plan --write --json
```

Fixtures:

```text
not_adopted_project
old_dp_project_minimal
old_dp_project_with_legacy_verify
old_dp_project_with_legacy_decompose
old_dp_project_with_hooks
old_dp_project_with_agents_md
spec80_project_current
```

Acceptance:

```bash
pytest tests/test_adopt.py
pytest tests/test_migrate_aliases.py
make check
```

### M6: Progressive disclosure retrofit

Retrofit first:

```text
dp doctor
dp campaign status
dp loop next
dp goal status
dp goal verify
dp evidence run
```

Acceptance:

```bash
pytest tests/test_progressive_disclosure.py
pytest tests/test_token_budgets.py
make check
```

### M7: Skills scaffold, lint, audit, and eval

Commands:

```bash
dp skills scaffold --target repo --json
dp skills lint --json
dp skills audit --json
dp skills eval --json
```

Acceptance:

```bash
pytest tests/test_skills.py
make check
```

### M8: Hook audit and scaffold

Commands:

```bash
dp hooks audit --json
dp hooks doctor --json
dp hooks scaffold --target git --json
dp hooks scaffold --target codex --json
```

Acceptance:

```bash
pytest tests/test_hooks.py
make check
```

### M9: Adoption apply and verify

Commands:

```bash
dp adopt apply <plan.json> --json
dp adopt verify --json
```

Acceptance:

```bash
pytest tests/test_adopt_apply.py
make check
```

### M10: Agent usability eval suite

Command or test suite:

```bash
dp agent eval --json
```

Acceptance:

```bash
pytest tests/test_agent_usability_evals.py
make check
```

## 18. Backward compatibility

Rules:

1. Existing commands keep their core result payloads unless explicitly versioned.
2. Envelope support should be additive or opt-in where necessary.
3. If output changes are unavoidable, support a compatibility path.
4. Existing AGENTS.md files are preserved.
5. Existing hooks are audited before replacement.
6. Existing specs, ADRs, Beads tasks, policies, and campaigns are preserved.
7. Legacy artifacts are migrated only through an explicit plan.
8. Old projects can still run `dp doctor --json`.
9. Adoption remains useful even without full campaign adoption.
10. `dp migrate` remains available if existing docs or users rely on that verb, even if `dp adopt` becomes canonical.

## 19. Documentation

Add or update:

```text
docs/specs/SPEC-81-agent-experience-layer.md
docs/reference/agent-response-contract.md
docs/reference/toolcards.md
docs/reference/hint-codes.md
docs/reference/agent-bootstrap.md
docs/reference/agent-capabilities.md
docs/reference/instruction-governance.md
docs/reference/adoption-workflow.md
docs/reference/skills.md
docs/reference/hook-governance.md
docs/reference/agent-usability-evals.md
docs/runbooks/adopting-dp-in-existing-project.md
docs/runbooks/agent-session-bootstrap.md
docs/runbooks/agent-session-handoff.md
docs/runbooks/debugging-agent-handoffs.md
```

Docs should be layered:

* AGENTS.md stays short.
* Skills stay short.
* Runbooks teach workflow.
* Reference docs define schemas.
* Specs explain why.

## 20. Acceptance criteria

SPEC-81 is complete when:

```bash
dp agent bootstrap --json --detail brief
dp agent capabilities --json
dp explain DP-HINT-EVIDENCE-MISSING --json
dp instructions inspect --json
dp instructions audit --json
dp adopt inspect --json
dp adopt plan --write --json
dp skills audit --json
dp hooks audit --json
make check
```

all succeed in the dp-codex repo, and fixtures prove:

1. Existing AGENTS.md files are preserved.
2. Nested instructions are discovered and precedence is represented.
3. Existing stricter project rules are not weakened.
4. Old dp projects receive adoption plans, not surprise rewrites.
5. Agent-facing responses include summaries, affordances, next actions, hints, artifacts, and expansions.
6. High-leverage commands support detail modes.
7. Token budgets are enforced by tests.
8. Skills are small, valid, trigger-specific, and eval-tested.
9. Hooks are audited and scaffolded conservatively.
10. Capabilities expose ToolCards with mutability and safety metadata.
11. Migration aliases remain compatible where needed.
12. Golden agent transcripts show an agent can bootstrap, claim, repair, block, and hand off without relying on chat memory.

## 21. Final instruction

Do not make dp louder.

Make it more usable by agents under pressure.

A good dp command should feel like a well-designed tool call: compact, typed, truthful about side effects, explicit about the next safe move, and expandable when detail is needed.

SPEC-80 made dp the campaign control plane.

SPEC-81 makes dp a high-quality agent experience.
