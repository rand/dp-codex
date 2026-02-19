# ADR Workflow Runbook

`dp adr` manages Architecture Decision Records under `docs/adr/`.

## File Convention

1. Path pattern: `docs/adr/ADR-XXXX-<slug>.md`
2. Front matter keys (required): `id`, `title`, `status`, `created`, `updated`, `superseded_by`
3. Body sections: `## Context`, `## Decision`, `## Consequences`

## Lifecycle

Valid statuses:

1. `proposal`
2. `accepted`
3. `superseded`
4. `deprecated`

Allowed transitions:

1. `proposal` -> `proposal`, `accepted`, `deprecated`
2. `accepted` -> `accepted`, `superseded`, `deprecated`
3. `superseded` -> `superseded`
4. `deprecated` -> `deprecated`

`superseded` transitions require `--superseded-by ADR-XXXX`.

## Commands

```bash
dp adr create "Adopt uv for tooling"
dp adr list
dp adr show ADR-0001
dp adr update ADR-0001 --status accepted
dp adr update ADR-0001 --status superseded --superseded-by ADR-0002
```
