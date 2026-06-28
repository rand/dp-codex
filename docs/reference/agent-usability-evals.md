# Agent Usability Evals

`dp agent eval --json` runs deterministic local checks for the SPEC-81 agent interface.

Categories:

- bootstrap-first-command
- next-action-quality
- error-repair-routing
- instruction-preservation
- legacy-project-adoption
- skill-triggering
- hook-audit-correctness
- token-budget-compliance
- resume-after-compaction
- no-ready-loop-handling

The eval includes a compact golden transcript that starts with bootstrap, discovers instructions,
claims work, handles evidence failure, explains a hint, blocks or repairs, and returns to bootstrap.

Executable evals also include fixture-backed `transcripts`. Each transcript has:

- `id`: category identifier.
- `fixture`: local fixture repository name or `builtin` for in-process fixtures.
- `ok`: whether all transcript steps matched expectations.
- `steps`: compact command observations with `command`, `exit_code`, `ok`, and `summary`.

Failure-oriented steps include stable error or hint fields so agents have a
repair route without expanding the full payload.
