# Governance And Risk Model

Governance in DP-Codex is not about control theater. It is about lowering risk while keeping delivery velocity realistic.

## Policy Modes

1. `strict`: all configured checks block on failure.
2. `guided`: high-value checks block; others can be advisory/disabled.
3. `minimal`: narrow safety net for fast-moving contexts.

Policy lives in `dp-policy.json`, which means governance is versioned and reviewable.

## Enforcement Surfaces

1. Local hooks (`pre-commit`, `pre-push`) catch issues before remote churn.
2. CI runs equivalent checks to avoid "works on my laptop" drift.

## Bypass Philosophy

Bypass exists for emergencies, not convenience.

1. Required env vars:
   `DP_BYPASS_ENFORCEMENT=1`
   `DP_BYPASS_REASON="<concrete reason>"`
2. Every bypass is logged to `.dp/bypass-log.jsonl`.
3. Follow-up remediation is mandatory.

This gives teams a pressure-release valve without erasing accountability.

## Risk Patterns

1. Over-strict policy can stall urgent fixes.
2. Over-minimal policy can normalize regressions.
3. Unreviewed bypasses can turn into silent policy erosion.

Good governance is adjustable, explicit, and auditable. Also mildly annoying in exactly the places where mistakes are expensive.
