# SPEC-70.02 Task Claim Intake

Status: active
Issue: dpcx-ea9.1
Parent: M7

[SPEC-70.02]

## Intent

Codex sessions need a low-friction task intake command that uses current Beads atomic claim
semantics and returns enough scoped context to start work without rediscovering the whole repo.

This is a wrapper over Beads, not a replacement for Beads. Beads remains the task authority.

## Commands

```bash
dp task claim --json
dp task claim <issue-id> --json
```

`dp task claim --json` delegates to:

```bash
bd ready --claim --json
```

`dp task claim <issue-id> --json` delegates to:

```bash
bd update <issue-id> --claim --json
```

Text output may stream Beads output for humans. JSON output MUST use dp's stable task envelope.

## Requirements

1. The command MUST use Beads atomic claim semantics.
2. The command MUST NOT implement a parallel claim store.
3. JSON output MUST include the delegated Beads command, raw claimed issue data, and extracted
   context.
4. Context extraction MUST be deterministic and local.
5. Context extraction SHOULD identify issue id, title, spec id, labels, description, design,
   acceptance criteria, parent, dependency/dependent ids, and likely repo paths mentioned in issue
   text.
6. Missing context MUST be surfaced as actionable guidance, not silent success.
7. Missing `bd`, missing `.beads`, and Beads command failures MUST preserve existing explicit exit
   semantics.
8. The command MUST NOT call an LLM.
9. `read_first` MUST be narrower than `mentioned_paths`: it may include resolved spec files and
   file-like paths, but MUST NOT include prose slash fragments or broad directories as files to read.

## Output Shape

```json
{
  "command": "task.claim",
  "ok": true,
  "exit_code": 0,
  "data": {},
  "stderr": null,
  "error": null,
  "context": {
    "issue_id": "dpcx-123",
    "title": "Implement feature",
    "spec_id": "SPEC-70.02",
    "labels": ["codex"],
    "read_first": ["docs/specs/SPEC-70-02-task-intake.md"],
    "mentioned_paths": ["dp/cli/main.py"],
    "warnings": []
  },
  "beads_command": ["ready", "--claim", "--json"]
}
```

## Formal Invariants

1. Delegation: every successful claim command is backed by exactly one Beads command invocation.
2. No hidden state: dp records no claim state outside Beads for task intake.
3. Deterministic context: `context(data)` is a pure function of the Beads JSON payload.
4. Failure preservation: a failed Beads claim produces no fabricated context that implies work was
   claimed.
5. Intake safety: path extraction filters absolute paths, parent traversal, URLs, shell-like flags,
   and non-file prose fragments before they can appear in `read_first`.

## Verification

Required evidence:

```bash
pytest tests/unit/test_cli_task.py
make check
dp trace validate --json
dp trace coverage --json
```
