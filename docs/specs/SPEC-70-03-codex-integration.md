# SPEC-70.03 Codex Repo Integration

Status: active
Issue: dpcx-ea9.2
Parent: M7

[SPEC-70.03]

## Intent

Codex-aware repositories need a low-friction integration point that reminds the agent to use dp's
disciplined workflow without turning every Codex turn into a heavy CI run.

The integration must be opt-in, deterministic, timeout-bounded, and safe to trust deliberately. It
must help a fresh Codex session discover local health, active Beads work, scoped context, and
evidence reminders from repo artifacts instead of relying on chat memory.

## Command

```bash
dp codex preflight --event stop --json
dp codex preflight --event session_start --json
dp codex preflight --event stop --strict --json
```

`preflight` is the command project-local Codex hooks or humans can call. It is not a Codex hook by
itself; hook installation remains an explicit adopting-repo choice.

## Requirements

1. The command MUST be deterministic, local, and LLM-free.
2. The command MUST NOT mutate Beads, git, campaign state, goal state, or evidence artifacts.
3. The command MUST use read-only Beads status where Beads data is needed.
4. The command MUST emit stable JSON with explicit exit semantics.
5. The command MUST support `guided` default behavior where missing workflow context is advisory.
6. The command MUST support `--strict` behavior where missing critical context can block.
7. The command SHOULD report current Beads health from `dp doctor` semantics.
8. The command SHOULD report active claimed Beads work when present.
9. The command SHOULD report changed files from git status and evidence signals from those paths.
10. The command SHOULD warn when code or scripts changed without any obvious test, evidence, or docs
    proof surface in the same working tree.
11. The command MUST keep hook runtime cheap and bounded by using only local command probes.
12. Repo-scoped Codex hook/config examples MUST be documented as opt-in and trust-gated.

## Output Shape

```json
{
  "command": "codex.preflight",
  "event": "stop",
  "mode": "guided",
  "ok": true,
  "exit_code": 0,
  "blocking_count": 0,
  "advisory_count": 1,
  "active_issue": {
    "id": "dpcx-ea9.2",
    "title": "M7.3 Add Codex hooks and repo config integration",
    "spec_id": "SPEC-70.03",
    "status": "in_progress"
  },
  "changed_files": ["dp/cli/main.py", "tests/unit/test_cli_codex.py"],
  "evidence": {
    "has_code_changes": true,
    "has_test_changes": true,
    "has_evidence_artifact_changes": false,
    "has_docs_changes": false,
    "missing_evidence_signal": false
  },
  "checks": [
    {
      "id": "beads_health",
      "status": "passed",
      "severity": "blocking",
      "message": "Beads health is ok."
    }
  ],
  "next_commands": ["dp doctor --json", "make check"]
}
```

## Exit Semantics

1. `0`: no blocking findings.
2. `1`: blocking findings exist.
3. `2`: unsupported event, malformed options, or incomplete input.

## Formal Invariants

1. Read-only invariant: `preflight` executes no Beads mutation commands, no git mutation commands,
   no evidence execution, and no goal or campaign state transitions.
2. Guided invariant: in guided mode, missing active work and missing evidence signals are advisory.
3. Strict invariant: in strict mode, missing active work and missing evidence signals for changed
   code or scripts are blocking.
4. Evidence-signal invariant: path-based evidence hints are never proof of completion; they are
   reminders to run and record real checks before closeout.
5. Hook trust invariant: checked-in docs may show project-local Codex hook config, but dp does not
   silently install or trust Codex hooks.

## Verification

Required evidence:

```bash
pytest tests/unit/test_cli_codex.py tests/unit/test_output_schemas.py
dp codex preflight --event stop --json
dp trace validate --json
dp trace coverage --json
make check
```
