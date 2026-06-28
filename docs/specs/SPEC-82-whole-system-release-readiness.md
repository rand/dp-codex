# [SPEC-82.01] Whole-System Release Readiness

## Purpose

Define the minimum proof obligations before dp-codex can be described as release-ready after the
SPEC-80 campaign-control and SPEC-81 agent-experience work.

## Scope

This spec covers the public dp-codex surface as a whole:

1. CLI command surface.
2. Documentation and reference indexes.
3. Package version and release-status claims.
4. Outside-repository install and use smoke checks.
5. Explicit non-goals for autonomous runners, MCP, and plugin distribution.

## Invariants

1. Every public argparse leaf command is documented in `docs/reference/cli-workflow-reference.md`.
2. Release-readiness documentation names the current package version from `pyproject.toml`.
3. Release-readiness documentation distinguishes implemented CLI-first behavior from deferred
   MCP, plugin, and background autonomy work.
4. Outside-repository smoke checks are documented for `dp --help`, `dp doctor --json`,
   `dp agent bootstrap --json --detail brief`, and `dp agent capabilities --json`.
5. The final release gate remains deterministic: `make check`, `dp review --json`,
   `dp verify --json`, `dp doctor --json`, and Beads tracker health must pass.

## Proof Obligations

1. A test introspects `dp.cli.main._build_parser()` and fails when a public leaf command is missing
   from the CLI workflow reference.
2. A test compares the package version in `pyproject.toml` with the release-readiness document.
3. A test checks that the release-readiness document includes the outside-repository smoke commands
   and deferred-surface boundaries.

## Non-Goals

SPEC-82.01 does not ship MCP, plugin packaging, hosted services, a dashboard, or direct background
agent execution.
