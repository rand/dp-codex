# SPEC-81.02 Agent Recovery and Collaboration Discipline

Status: implemented
Depends on: SPEC-81 Agent Experience Layer
Trace: `SPEC-81.02`

## Objective

Make dp-facing agents distinguish a failed completion gate from a true blocker. Agents must perform
bounded, authorized diagnosis and repair when that can be done without changing the goal's meaning,
scope, or evidence standard. Purposeful consultation should improve diagnosis and review without
becoming decision authority or verification evidence.

## Recovery Contract

For an observed failure `F`, the acting agent must capture the exact command, exit code, failing
check, current branch/HEAD, relevant GoalContract boundaries, and existing failed receipt before
changing state.

The agent classifies `F` by taking the first matching case in this order:

1. `invalid_execution`: no trustworthy verdict exists because invocation, environment, cache,
   lease, worktree, or tool state is invalid.
2. `repairable_failure`: a deterministic failure has a smallest safe repair authorized by local
   law and the GoalContract.
3. `independent_repair`: the defect is non-semantic but its owner or required paths are outside the
   active contract, and another owner or repair goal can fix it without a human semantic or
   authority decision.
4. `true_blocker`: progress requires a new public-behavior, schema, exit-code, DoD, authority,
   external-dependency, validator, or unsafe-scope decision, or the declared attempt budget is
   exhausted. A missing validator is a true blocker only when no authorized in-scope or known
   independent repair route exists.

A repair is admissible only when it:

- stays inside applicable instructions and allowed paths;
- preserves tests, validators, contracts, and evidence strength;
- is reversible through normal version-control operations;
- states a concrete hypothesis and predicted focused observation; and
- remains within `iteration_policy.max_attempts` when the GoalContract declares one.

The smallest discriminating check runs first. After a repair, the agent reruns the exact failed
check, then the full required evidence ladder. An unchanged action may not be repeated unless
relevant state or the hypothesis changed. Failed receipts remain historical evidence.

A failed gate blocks completion, not diagnosis or authorized repair. Verification still determines
done. Consultation, narration, and agent consensus never do.

## Collaboration Contract

Use caller-platform sub-agents or external specialists when work has independent diagnostic
threads, domain-specific risk, context pressure, or needs adversarial review. Each delegation must
state its question, read/write scope, forbidden actions, expected evidence, and stop condition.

The primary agent owns the dp claim, lifecycle transitions, adopted edits, tracker truth, and final
verification. Helpers are read-only by default. A writing helper requires an isolated worktree or
branch and disjoint paths. External model output is advisory and must not receive repository
material without applicable authorization.

Unavailable consultation must not block otherwise ready work. Delegation without a decision-
relevant finding is performative and should not be repeated.

## Deterministic Surfaces

1. Goal emission includes failure classification, repair admission, attempt budget, and conditional
   blocker routing.
2. Instruction audit identifies dp-aware guidance missing recovery or collaboration discipline and
   `plan-update` proposes additive text without mutation.
3. Stable hints state that evidence failure blocks completion but permits authorized repair.
4. Agent evals separately exercise repairable failure, true blocker routing, and purposeful
   collaboration.
5. Repo-scoped skills teach the same protocol while preserving `AGENTS.md` precedence.

## Non-Goals

- Do not weaken gates or reinterpret failed evidence as success.
- Do not expand GoalContract authority or allow helpers to share overlapping writes.
- Do not turn dp into a background agent runner.
- Do not make any external model, hook, or skill a blocking verification dependency.
- Do not change blocker lifecycle semantics in this slice.

## Acceptance

1. Focused tests fail if the golden agent flow jumps directly from evidence failure to blocking.
2. Emitted goals expose `max_attempts` and the repair-versus-blocker boundary.
3. Instruction plans and checked-in skills contain compact recovery and collaboration guidance.
4. Recovery metrics are derived from evaluated transcript outcomes rather than hard-coded success.
5. The tracked global guidance can be reviewed, installed, and reverted independently.
