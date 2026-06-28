# MIGRATION-2026-06-28-agent-experience

Status: planned
Source classification: current_spec81

## Changes

- `create-goal-event-dir` mkdir `.dp/goals` (apply): Enable append-only goal lifecycle events.
- `create-campaign-event-dir` mkdir `.dp/campaigns` (apply): Enable append-only campaign handoff events.

## Conflicts

- None.

## Verification

- `dp instructions audit --json`
- `dp agent bootstrap --json --detail brief`
- `dp doctor --json`
- `dp adopt verify --json`
