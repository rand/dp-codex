# Command Runtime And Exit Semantics

This document describes how commands are dispatched and how outcomes are encoded.

## Dispatch Model

1. `dp.cli.main._build_parser` defines command trees.
2. Each subcommand binds a concrete handler via `set_defaults(handler=...)`.
3. Handlers return integer exit codes and write text/json outputs.

## Exit-Code Conventions

1. `0`: command completed successfully.
2. `1`: command completed but produced blocking/failed outcome.
3. `2`: usage, validation, or incomplete-state errors where relevant.
4. `127`: required external command unavailable (notably provider commands).

## Deterministic Output Rules

1. JSON output should be stable and sort keys where practical.
2. Human text output should summarize results and actionable next steps.
3. Error paths should include concrete causes, not generic failure text.

## Goal Runtime

`dp goal` commands preserve the same exit-code model:

1. `dp goal lint` returns `0` for valid contracts, `1` for invalid contracts, and `2` for malformed or unsupported input.
2. Mutating goal lifecycle commands validate the GoalContract before appending events.
3. Goal lifecycle state is reconstructed from `.dp/goals/events.jsonl`.
4. `dp goal complete` records `evidence_pending`; it does not declare behavioral verification.
5. `dp goal verify` consumes a `dp evidence run` artifact and appends `verified` only when the
   run passed, goal id matches, the EvidencePlan path matches the GoalContract, and the current
   EvidencePlan hash matches the run.

## Evidence Runtime

`dp evidence lint` validates EvidencePlan files without executing checks:

1. `0`: valid evidence plan.
2. `1`: loaded JSON, but invalid plan.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete input.

`dp evidence run` first applies the same lint gate. If lint fails, no checks are executed and the
lint exit code is preserved. If lint succeeds, the executor runs registered argv-array checks with
`shell=False`, declared timeouts, existing relative cwd values, a controlled environment allowlist,
and typed assertions:

1. `0`: every check passed.
2. `1`: a loaded plan is invalid, or a valid check failed, timed out, or could not run safely.
3. `2`: missing file, malformed JSON, non-object JSON, unsupported schema, or incomplete input.

Evidence runtime does not call an LLM, execute raw shell strings, or mark goals verified.
Run output records the source EvidencePlan path and sha256 so goal verification can reject stale or
mismatched evidence.

## Campaign Init Runtime

`dp campaign init` is an authoring command that writes deterministic draft artifacts from a local
primary spec. It hashes the primary spec, extracts Markdown sections and semantic signals, and then
lints the generated CampaignManifest, LoopLedger, GoalContracts, and EvidencePlans.

The compiler mode is `deterministic_markdown_signals`. It records requirement, evidence, decision,
blocker, and dependency cues, but it does not call an LLM, create Beads issues, execute evidence,
mark work verified, or infer LoopLedger dependency edges from prose. Generated campaign state stays
`draft`.

`dp campaign refine` is the next authoring step. Dry-run mode emits a plan and writes nothing.
`--write` creates deterministic child spec/ADR stubs, updates GoalContract and EvidencePlan
refinement metadata, and records artifact paths in the CampaignManifest while preserving `draft`
status. `--create-beads` requires `--write` and explicitly materializes Beads epic/issues through
the Beads provider.

`dp campaign refine --llm --json` emits a deterministic request package for the provider currently
in use by the calling agent. dp does not make the network/model call in this path. The calling agent
writes a response artifact, and `dp campaign refine --llm-response <path> --write --json` imports
that artifact only after deterministic validation of campaign id, prompt hash, provider provenance,
known goal ids, path sanity, and argv-only evidence proposals without raw shell syntax. Imported
model content remains draft authoring metadata; it must not run in hooks/CI or make verification
judgments.

## Loop Runtime

`dp loop` commands operate over explicit LoopLedger files and append-only goal events:

1. `dp loop lint` returns `0` for valid ledgers, `1` for invalid loaded ledgers, and `2` for
   malformed or unsupported input.
2. `dp loop status` validates the ledger and reconstructs each node state from referenced
   GoalContracts and `.dp/goals/events.jsonl`.
3. `dp loop next` returns the first ready unclaimed node in ledger order.
4. `dp loop next --claim` writes through the existing `dp goal claim` event path.
5. `dp loop next --emit codex` packages the selected GoalContract as a Codex-operable handoff.

Loop commands do not compile primary specs, call an LLM, run agents, or execute evidence
implicitly. Evidence execution is explicit through `dp evidence run`.

## Provider Boundary

`/dp/providers/beads.py` wraps `bd` execution and normalizes failure classes:

1. `BdUnavailableError`
2. `BeadsNotInitializedError`

The CLI layer translates those into consistent exit codes and user-facing messages.
`dp doctor` parses `bd version` before modeling optional sync capability. Beads 1.0+ is treated as
having no `bd sync` command by design, so the absence is reported as
`sync_command_available=false` without a warning. Current Beads probes use read-only sandbox mode
where supported.

## Enforcement Runtime

`dp enforce` delegates to `/dp/enforcement/engine.py`.

1. Stage-specific check order (`pre-commit`, `pre-push`).
2. Policy-driven blocking/skip behavior.
3. Bypass handling via environment variables.
4. Audit logging to `.dp/bypass-log.jsonl`.
