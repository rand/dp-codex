# ToolCards

`dp agent capabilities --json` emits `dp.capabilities.v1`.

Each ToolCard describes a command as an agent-usable capability:

- `name`
- `purpose`
- `phase`
- `output_schema`
- `mutability`
- `idempotent`
- `destructive`
- `open_world`
- `requires_trust`
- `cost`
- `common_next`

ToolCards are affordances, not permissions. They help agents choose cheap orientation commands,
avoid accidental mutation, and discover expansion paths before consuming large context.
