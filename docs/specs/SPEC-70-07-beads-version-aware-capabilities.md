# SPEC-70.07 Beads Version-Aware Capabilities

Status: active
Issue: dpcx-ea9.7
Parent: M7

[SPEC-70.07]

## Intent

dp must interact with current Beads versions without assuming stale command surfaces. In Beads
1.0+, `bd sync` is intentionally absent. `dp doctor` should model that as an expected capability
shape, not as a health warning or a command to probe.

## Requirements

1. `dp doctor --json` MUST parse the installed `bd version` output when possible.
2. For parsed Beads versions where `bd sync` is known removed, dp MUST NOT run `bd sync --help`.
3. For current Beads 1.0+ versions, `sync_command_available` MUST be `false` without adding a
   warning.
4. For older or unparseable Beads versions, dp MAY probe `bd sync --help` to preserve
   compatibility.
5. Missing `bd`, missing `.beads`, and unusable Beads databases MUST retain explicit recovery
   guidance.
6. Hooks and CI MUST continue using `dp doctor --json` as a deterministic read-only health gate,
   not hidden sync or persistence.
7. For current Beads versions that support sandbox mode, doctor probes SHOULD use read-only
   sandboxed commands.

## Non-Goals

1. No Beads mutation.
2. No replacement for `bd export`, `bd backup`, `bd vc`, or `bd bootstrap`.
3. No network checks.
4. No removal of the legacy `sync_command_available` JSON field.

## Verification

Required evidence for this slice:

```bash
pytest tests/unit/test_beads_provider.py tests/unit/test_cli_task.py
dp doctor --json
make check
```
