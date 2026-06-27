# SPEC-70.04 Harden Verification Evidence

Status: active
Issue: dpcx-ea9.3
Parent: M7

[SPEC-70.04]

## Intent

SPEC-80 depends on evidence that survives agent sessions and can be checked by deterministic gates.
The legacy `dp verify` manifest format is useful, but its artifact level previously proved only that
an artifact path existed. That is too weak for campaign closeout: a file can exist while the command
that produced it failed, while the file content changed after review, or while the artifact is not
traceable to the Beads issue or spec it claims to support.

`dp verify` must therefore support structured evidence records while preserving existing simple
manifests. This is still structural/provenance verification, not arbitrary command execution.

## Requirements

1. Existing manifests with `truths`, `artifacts`, and `links` MUST remain valid.
2. Artifact records with only `id` and `path` MUST continue to verify by existence.
3. When an artifact declares `sha256`, `dp verify` MUST compute the artifact digest and fail on
   mismatch.
4. When an artifact declares `command`, it MUST be a recorded command object, not a shell string.
5. A command record MUST include `argv`, `exit_code`, and `success_exit_codes`.
6. A command record MUST fail verification when `exit_code` is not included in
   `success_exit_codes`.
7. Command `argv` MUST be an array of non-empty strings.
8. `dp verify` MUST NOT execute commands from manifest JSON.
9. When an artifact declares `task_id`, it MUST look like a Beads issue id.
10. When an artifact declares `spec_id`, it MUST look like a traceable spec id such as
    `SPEC-70.04`.
11. Link validation MUST continue to ensure truth and artifact references resolve.
12. JSON output and exit codes MUST remain stable:
    1. `0`: verified.
    2. `1`: failed.
    3. `2`: incomplete or malformed command input.

## Manifest Shape

The default manifest remains `docs/verify/manifest.json`.

```json
{
  "truths": [{"id": "T1", "verified": true}],
  "artifacts": [
    {
      "id": "A1",
      "path": "docs/evidence-runs/RUN-GOAL-example.json",
      "sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "command": {
        "argv": ["dp", "evidence", "run", "docs/evidence/EVIDENCE-example.json", "--json"],
        "exit_code": 0,
        "success_exit_codes": [0],
        "cwd": "."
      },
      "task_id": "dpcx-ea9.3",
      "spec_id": "SPEC-70.04"
    }
  ],
  "links": [{"truth_id": "T1", "artifact_id": "A1"}]
}
```

## Non-Goals

1. Do not turn manifest verification into an evidence executor.
2. Do not allow raw shell strings as executable instructions.
3. Do not require legacy adopters to migrate before `dp verify` continues to work.
4. Do not use an LLM to decide evidence validity.
5. Do not make hooks or CI invoke network/model calls.

## Formal Invariants

1. **No-execution invariant:** for every manifest `M`, `dp verify --manifest M` may read files
   referenced by artifacts but must not execute commands described by `M`.
2. **Legacy-compatibility invariant:** a manifest artifact with only `id` and an existing `path`
   remains sufficient for the artifact level to pass.
3. **Configured-evidence invariant:** if an optional structured evidence field is present, that
   field is enforced and can fail the artifact level.
4. **Digest-determinism invariant:** `sha256` validity is a pure function of the artifact bytes and
   the manifest digest string.
5. **Command-record invariant:** command evidence records describe completed command observations;
   they are never instructions to execute.

## Verification

Required evidence:

```bash
pytest tests/unit/test_verify.py tests/unit/test_output_schemas.py tests/unit/test_cli_verify.py
dp trace validate --json
dp trace coverage --json
make check
```
