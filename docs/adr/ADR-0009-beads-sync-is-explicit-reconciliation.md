# ADR-0009: Beads Sync Is Explicit Reconciliation

Status: accepted
Date: 2026-06-27
Spec: [SPEC-80.18](../specs/SPEC-80-18-beads-lifecycle-synchronization.md)

## Context

SPEC-80 makes dp responsible for campaign contracts, evidence, lifecycle events, and recovery.
Beads remains the repository's issue/dependency substrate. Those two systems must stay aligned, but
they have different authority:

1. dp goal events decide campaign execution state.
2. dp evidence artifacts decide verification.
3. Beads issues and dependencies decide work queue and issue graph visibility.

If dp silently mutates Beads inside every goal transition, dry-run commands become harder to trust
and failed Beads writes can obscure the canonical dp event. If dp never syncs to Beads, campaigns
become a parallel tracker.

## Decision

Beads lifecycle synchronization is an explicit reconciliation command:

```bash
dp campaign sync-beads <campaign.json> --json
dp campaign sync-beads <campaign.json> --write --json
```

Dry-run mode plans operations without mutation. Write mode applies the plan through current Beads
commands and returns per-operation results. Normal goal commands continue to append dp events first;
they do not hide Beads side effects.

## Consequences

1. Agents and humans can inspect the sync plan before mutating Beads.
2. Campaign state remains recoverable from dp artifacts even when Beads is temporarily unavailable.
3. Beads remains the external issue/dependency graph and can be updated deliberately.
4. Tests can mock a small set of Beads commands instead of needing a live tracker for every goal
   transition.
5. Later managed runners can call sync points explicitly after start/block/release/verify actions.

## Rejected Alternatives

1. **Implicit Beads writes in every goal command.** Rejected because hidden mutation makes local
   recovery and failure modes less transparent.
2. **Treat Beads as read-only after campaign refine.** Rejected because the campaign would stop
   feeding its operational state back into the issue substrate.
3. **Replace Beads with dp loop state.** Rejected because SPEC-80 explicitly preserves Beads as the
   task/dependency layer.
