# ADR-0015: Failed Gates Block Completion, Not Authorized Repair

Status: accepted
Date: 2026-07-15
Spec: [SPEC-81.02](../specs/SPEC-81-02-agent-recovery-and-collaboration-discipline.md)

## Context

dp correctly refuses verification when evidence fails and records blockers durably. Its canonical
agent transcript nevertheless moved directly from evidence failure to `needs_validator`. That
teaches agents to treat a repairable implementation or environment defect as a terminal blocker.
Conversely, unbounded retry language can encourage repeated actions without information gain.

Agent collaboration also needs an ownership boundary. Independent diagnosis and adversarial review
can save context and expose mistakes, but agent consensus is not evidence and concurrent edits can
corrupt scope ownership.

## Decision

A deterministic gate failure blocks completion immediately. It does not block diagnosis or the
smallest reversible repair already authorized by project law and the GoalContract.

Agents use the SPEC-81.02 classification before blocking. They do not repeat unchanged actions,
weaken acceptance, or exceed the declared attempt budget. Out-of-scope non-semantic defects become
separate repair work; semantic or authority gaps become durable blockers.

The primary agent remains the single owner of the claim, lifecycle, integrated edits, and
verification. Read-only specialists and adversarial reviewers are encouraged for genuinely
separable questions. Writing helpers require isolated worktrees and disjoint ownership. External
agent output is advisory.

## Consequences

- Ordinary failures lead to diagnosis and an authorized repair attempt instead of reflexive stop.
- True blockers remain explicit, durable, and verification-safe.
- Retry loops must produce new information or stop.
- Consultation can reduce context pressure without expanding authority.
- dp remains a deterministic control plane, not an autonomous runner.

## Rejected Alternatives

1. **Block on every red gate.** Rejected because it strands goal-local defects and confuses
   completion state with repair authority.
2. **Retry until green.** Rejected because it permits loops, scope drift, and acceptance weakening.
3. **Let a panel of agents decide done.** Rejected because verification artifacts and repo gates are
   the authority.
4. **Add background orchestration to dp.** Rejected because caller platforms can coordinate agents
   while dp keeps state and evidence deterministic.
