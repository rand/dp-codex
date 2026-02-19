# Migration Guide

Use this checklist to migrate an existing repository to `dp-codex`.

## 1. Prerequisites

1. Install `python3` (3.11+), `uv`, `make`, and `bd`.
2. Add this repository as a dependency or ensure `dp` CLI is available on PATH.

## 2. Repository Bootstrap

1. Add policy file:

```json
{
  "mode": "guided",
  "overrides": {
    "review": true,
    "verify": true
  }
}
```

2. Add verification manifest at `docs/verify/manifest.json`.
3. Ensure `Makefile` includes `lint`, `typecheck`, and `test` targets.
4. If needed, initialize Beads:

```bash
bd init -p <repo-prefix>
```

## 3. Hook Installation

```bash
./hooks/install.sh
```

## 4. Smoke Validation

Run this sequence in the migrated repository:

```bash
make check
dp trace coverage --json
dp trace validate --json
dp enforce pre-commit --policy dp-policy.json --json
dp review --json
dp verify --json
dp enforce pre-push --policy dp-policy.json --json
```

## 5. Pilot Rollout

1. Select one real feature as migration pilot.
2. Track tasks through `dp task` wrappers.
3. Record pilot evidence and friction in `docs/pilot/`.
4. Expand rollout after pilot succeeds with no open high-severity defects.

## 6. Rollback Strategy

If migration blocks urgent delivery:

1. Use bypass once with reasoned audit:

```bash
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="emergency fix" git push
```

2. Record remediation task before ending the session.
3. Re-run enforcement checks after the emergency change lands.
