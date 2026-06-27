# Field Report CLI

## Product Objective

Build a small command-line tool named `field-report` for operations teams that collect structured
reports from field technicians.

The tool must read a local JSON file, normalize required fields, and print a canonical JSON document
to stdout. It should be useful in any repository, not tied to dp-codex internals.

## Requirements

The CLI must require:

- `site_id`
- `reported_at`
- `severity`
- `summary`

The CLI should reject missing required fields with a non-zero exit code and an operator-readable
error message.

The CLI should preserve unknown fields under `metadata` so field teams do not lose context.

Depends on a decision about whether `severity` is a fixed enum or a free-form string.

## Evidence And Validation

Acceptance requires deterministic checks:

- a unit test for valid report normalization
- a unit test for missing required fields
- a JSON schema or typed validator for the canonical output
- a smoke command that proves the CLI can read an input file and print valid JSON

## Open Decision

Decide whether the first version should enforce a severity enum. The default proposal is:

- `info`
- `warning`
- `critical`

Risk: a strict enum may reject useful field reports before the operations team agrees on taxonomy.

## Rollout Notes

Ship the first version behind a documented local command. Do not add a network service, database, or
background worker in the first implementation.
