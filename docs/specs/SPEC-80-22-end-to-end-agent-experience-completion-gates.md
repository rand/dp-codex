# SPEC-80.22 End-to-End Agent Experience Completion Gates

Status: active
Issue: dpcx-pb5.19
Parent: SPEC-80

[SPEC-80.22]

## Intent

SPEC-80 is not complete when the core campaign JSON contracts exist. It is complete only when a
human and a Codex session can operate the disciplined process end to end with low enough friction
that the control plane is actually usable in adopting repositories.

The modernization work previously tracked as M7 is therefore a SPEC-80 completion dependency, not
adjacent cleanup. Current Beads claim ergonomics, Codex repo integration, hardened evidence,
flow-level pilots, and packaging decisions are required for the full campaign-control experience.

## Required Completion Gates

1. **Task intake gate.** Codex can claim Beads work through current Beads semantics and receive
   scoped context without full-repo rediscovery.
2. **Codex integration gate.** Repo-scoped Codex instructions, hooks, or config examples are
   explicit, opt-in, timeout-bounded, and deterministic.
3. **Evidence quality gate.** General verification surfaces move beyond path existence where
   configured and can validate structured command, hash, task, and spec evidence.
4. **Flow pilot gate.** At least one realistic adopting-project flow measures setup recovery,
   claim latency, evidence completeness, blocker routing, closeout, and false-positive friction.
5. **Packaging gate.** dp has an ADR-quality decision for CLI-only, Codex skill, MCP, or plugin
   packaging, with any chosen scaffold documented and safe to install.
6. **Primary-spec benchmark gate.** Campaign intake and refinement are tested against realistic
   primary-spec shapes: concise roadmap specs and large architecture/system specs.
7. **Recovery gate.** A fresh Codex session can recover active, blocked, evidence-pending, ready,
   and verified campaign states from repo artifacts without chat memory.

## Required Related Work

The following existing Beads work is in-scope for SPEC-80 completion:

1. `dpcx-ea9.1` / SPEC-70.02 task claim ergonomics and context extraction.
2. `dpcx-ea9.2` / SPEC-70.03 Codex hooks and repo config integration.
3. `dpcx-ea9.3` / SPEC-70.04 hardened verification evidence.
4. `dpcx-ea9.4` / SPEC-70.05 flow pilots and friction metrics.
5. `dpcx-ea9.5` / SPEC-70.06 skill, MCP, and plugin packaging evaluation.

SPEC-70.06 is satisfied when an ADR-quality packaging comparison exists, the chosen scaffold is
checked in and documented, and tests prove the scaffold preserves dp's deterministic gate boundary.

## Closure Evidence

As of 2026-06-27, the SPEC-80.22 gate is satisfied by these repo artifacts and Beads closures:

1. `dpcx-ea9.1` / SPEC-70.02 task intake is closed with `dp task claim` context extraction over
   current Beads claim semantics.
2. `dpcx-ea9.2` / SPEC-70.03 Codex integration is closed with deterministic preflight and
   opt-in hook/config guidance.
3. `dpcx-ea9.3` / SPEC-70.04 evidence quality is closed with structured verify-manifest evidence.
4. `dpcx-ea9.4` / SPEC-70.05 flow evals are closed with deterministic doctor/claim/verify/close
   friction metrics.
5. `dpcx-ea9.5` / SPEC-70.06 packaging is closed with ADR-0014, CLI-first guidance, and the
   repo-local `dp-campaign-control` skill scaffold.
6. `dpcx-pb5.18` / SPEC-80.21 primary-spec intake UX is closed with dry-run preview, source
   provenance, unsupported URL diagnostics, and large-spec preview fields.
7. `dpcx-pb5.9` / SPEC-80.09 semantic compiler hardening is closed with bounded signal excerpts
   and local Waveguide/Supastructure-style dry-run benchmarks.

The large-spec benchmark found and fixed a real agent-experience issue: unbounded paragraph cues in
dry-run compiler JSON. `dp campaign init` now caps individual signal cues at 220 characters while
leaving the primary spec as the source of truth.

SPEC-80 may depend on these issues rather than duplicating their implementation. The important
rule is closure: the SPEC-80 epic must not close while those gates remain open or unproven.

## Non-Goals

1. Do not make hooks or CI call an LLM.
2. Do not replace Beads.
3. Do not require a hosted service for local campaign operation.
4. Do not make plugin, skill, or MCP packaging mandatory before the ADR establishes that it reduces
   friction and preserves safety.

## Verification

Required evidence:

```bash
bd list --parent dpcx-pb5 --json -n 0
bd list --parent dpcx-ea9 --json -n 0
pytest tests/test_campaign_pilot.py
make check
dp doctor --json
```
