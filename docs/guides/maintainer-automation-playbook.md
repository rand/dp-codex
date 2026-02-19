# Maintainer And Automation Playbook

Audience: maintainers responsible for policy, reliability, and release quality.

Goal: keep the system trustworthy under real delivery pressure.

## Governance Checklist

1. Keep `dp-policy.json` versioned and reviewed.
2. Ensure hooks are installed in active repos.
3. Keep CI parity with local enforcement commands.
4. Audit `.dp/bypass-log.jsonl` usage patterns.

## Operational Commands

```bash
make check
dp enforce pre-commit --policy dp-policy.json --json
dp enforce pre-push --policy dp-policy.json --json
scripts/run_pilot_migration.sh
```

## Release Discipline

1. Re-run pilot flow for release candidates.
2. Confirm no open high-severity core defects.
3. Publish readiness decision in release docs.
4. Keep migration and troubleshooting guides current.

## Emergency Handling

If normal gates are unsafe during incident mitigation:

```bash
DP_BYPASS_ENFORCEMENT=1 DP_BYPASS_REASON="incident mitigation" git push
```

Then:

1. Capture remediation task.
2. Restore normal policy path.
3. Re-run full enforcement checks.

## Automation Design Notes

1. Prefer `--json` outputs in scripted integrations.
2. Treat exit codes as the primary automation signal.
3. Keep scripts explicit; avoid hidden mutable environment assumptions.
4. Assume tired humans will debug this at inconvenient hours.
