# Task JSON Output Schema

All `dp task` subcommands support `--json` and return a stable envelope:

```json
{
  "command": "task.ready",
  "ok": true,
  "exit_code": 0,
  "data": {},
  "stderr": null,
  "error": null
}
```

## Fields

1. `command`: Fully qualified `dp` command identifier (`task.ready`, `task.show`, `task.update`, `task.close`, `task.discover`)
2. `ok`: Boolean success flag (`true` when exit code is `0`)
3. `exit_code`: Process exit code
4. `data`: Parsed JSON returned by `bd --json` when available
5. `stderr`: stderr text from `bd` when present, otherwise `null`
6. `error`: Wrapper-level failure message (for missing `bd` or missing `.beads`), otherwise `null`
7. `raw_output` (optional): Raw stdout if `bd --json` output cannot be parsed

## Error Behavior

1. Missing `bd`: `exit_code=127`, `ok=false`, `error` populated
2. Uninitialized `.beads`: `exit_code=2`, `ok=false`, `error` populated
3. `bd` command failure: non-zero `exit_code`, `ok=false`, stderr forwarded

For provider health and setup diagnostics, use `dp doctor --json`. Task wrappers
delegate to Beads; doctor checks whether that delegation is safe before work
starts.
