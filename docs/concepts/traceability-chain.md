# Traceability Chain

Traceability is the spine of DP-Codex. Without it, workflow artifacts become disconnected notes.

## Chain Of Evidence

1. Specs define intent: `[SPEC-XX.YY]`
2. Code and tests reference intent: `@trace SPEC-XX.YY`
3. Validation checks references resolve: `dp trace validate`
4. Coverage checks declared scope: `dp trace coverage`
5. Verify links goals to concrete artifacts: `dp verify`

## Why It Matters

1. It reduces accidental scope drift.
2. It exposes orphaned implementation work.
3. It improves review quality by tying code to purpose.

## Failure Modes And Signals

1. Unresolved trace references: implementation points to missing specs.
2. Uncovered specs: declared outcomes without implementation evidence.
3. Verify incomplete/failed: artifacts or links are missing.

## Design Guidance

1. Keep spec IDs stable once published.
2. Prefer small, cohesive specs over giant omnibus documents.
3. Treat unresolved trace findings as first-class defects.
4. Keep verification manifests close to the work they represent.
