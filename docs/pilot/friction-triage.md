# Pilot Friction And Defect Triage

Date: 2026-02-19
Owner: Rand Arete

## Summary

Pilot execution surfaced several high-impact friction points that were remediated in this session. No unresolved high-severity core defects remain.

## Findings

1. `F-001` (High): Trace validation produced false positives from Python string literals.
   Impact: Pre-commit enforcement blocked healthy repositories.
   Remediation: `dp/core/trace_parser.py` now tokenizes Python comments and ignores string literals for `@trace` extraction.
   Status: Resolved.
2. `F-002` (High): Review conflict-marker detection treated quoted example text as merge conflicts.
   Impact: Pre-push enforcement blocked valid repositories with documentation/test fixtures.
   Remediation: `dp/core/review.py` now requires conflict markers at line start (after whitespace), preventing quoted/example false positives.
   Status: Resolved.
3. `F-003` (Medium): Enforcement subcommands using `uv` failed in restricted environments without writable default cache.
   Impact: Hook and pilot execution failed in sandboxed environments.
   Remediation: `dp/enforcement/engine.py` sets `UV_CACHE_DIR` fallback to `<repo>/.uv-cache` when unset; hook scripts also export local fallback.
   Status: Resolved.
4. `F-004` (Medium): New adopters may run enforcement before `dp` is installed on PATH.
   Impact: Migration friction in external pilot repositories.
   Remediation: Added migration/troubleshooting runbooks and a reproducible pilot script with explicit bootstrap behavior.
   Status: Resolved for documented path.

## Severity Decision

1. High-severity core defects: `0` open
2. Medium-severity defects: `0` open
3. Remaining work: tracked as post-1.0 improvements only
