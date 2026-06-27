# SPEC-70.01 Beads Compatibility and Doctor Baseline

Status: active
Issue: dpcx-66l

[SPEC-70.01]

## Intent

dp-codex must tolerate current Beads CLI behavior without relying on stale
commands or hidden state changes. The baseline health path should make it clear
whether a Codex session can safely claim and close work before implementation
starts.

## Requirements

1. `dp doctor` MUST provide a read-only health check with stable JSON output.
2. Beads health checks MUST distinguish missing `bd`, missing `.beads`, and an
   initialized `.beads` directory whose database is not usable.
3. Beads health checks MUST probe current Beads commands in read-only mode when
   the command supports it.
4. The removed `bd sync` command MUST NOT be required by enforcement or docs.
5. When `bd sync` is unavailable, diagnostics MUST point users toward current
   Beads surfaces such as `bd status`, `bd export`, `bd backup`, `bd vc`, or
   `bd bootstrap`.
6. Pre-push task safeguards MUST check task provider health, not perform
   implicit sync or mutation.

Refinement: `[SPEC-70.07]` defines version-aware capability handling. For parsed Beads 1.0+
versions, absence of `bd sync` is expected and SHOULD NOT be emitted as a health warning.

## Exit Semantics

1. `dp doctor --json` exits `0` when required health checks pass.
2. `dp doctor --json` exits `2` when required health checks fail because the
   local workflow is unavailable or incomplete.
3. Warnings are advisory and do not fail the command unless they indicate that a
   required provider is unusable.
