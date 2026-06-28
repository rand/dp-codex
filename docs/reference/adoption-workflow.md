# Adoption Workflow

Adoption heals projects without erasing history.

Canonical flow:

```bash
dp adopt inspect --json
dp adopt plan --write --json
dp adopt apply docs/migrations/MIGRATION-...json --json
dp adopt verify --json
```

Compatibility aliases remain available under `dp migrate`.

Classifications:

- `not_adopted`
- `legacy_dp`
- `partial_spec80`
- `current_spec80`
- `current_spec81`
- `unknown`

Plans are additive by default. They may propose AGENTS.md patches, create event directories, and
scaffold focused repo skills through the known local `dp skills scaffold --target repo --json`
action, but they do not overwrite local instructions or execute arbitrary commands.
