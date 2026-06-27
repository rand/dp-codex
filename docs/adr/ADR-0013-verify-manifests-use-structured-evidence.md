# ADR-0013: Verify Manifests Use Structured Evidence Records

Status: accepted
Date: 2026-06-27
Spec: [SPEC-70.04](../specs/SPEC-70-04-evidence.md)

## Context

SPEC-80 makes dp the control plane for verified agent campaigns. That requires evidence that can be
recovered from repo artifacts and checked by deterministic commands. The original `dp verify`
manifest mode checked three levels: truth flags, artifact existence, and links between them. This
was intentionally simple, but path existence alone is not enough evidence quality for campaign
closeout.

At the same time, `dp verify --manifest` is not the security-sensitive evidence executor. That role
belongs to `dp evidence run`, which uses typed plans, argv arrays, allowlists, timeouts, and
assertions. Mixing execution into a legacy manifest verifier would blur dp's reliability boundary
and invite arbitrary shell execution from generated JSON.

## Decision

`dp verify --manifest` will remain a deterministic structural/provenance verifier. Legacy artifact
records with only `id` and `path` continue to pass by existence. When structured evidence fields are
present, they are enforced:

1. `sha256` must match the artifact bytes.
2. `command` must be a recorded object with `argv`, `exit_code`, and `success_exit_codes`.
3. `command.exit_code` must be in `command.success_exit_codes`.
4. `command` must not be a shell string.
5. `task_id` and `spec_id` must match known local identifier shapes.

The verifier reads artifacts and validates records. It does not execute commands from the manifest.

## Consequences

1. Existing projects keep working without immediate migration.
2. Campaign closeout can opt into stronger evidence without waiting for a full evidence executor
   integration.
3. Future Codex sessions can inspect command outcomes, hashes, Beads links, and spec links from
   durable JSON rather than chat memory.
4. Evidence execution and evidence verification remain separate responsibilities.

## Rejected Alternatives

1. **Require every artifact to include a hash and command record immediately.** Rejected because it
   would break existing simple manifests without adding a migration path.
2. **Execute command strings from verify manifests.** Rejected because generated JSON must not be an
   arbitrary shell execution surface.
3. **Treat command records as advisory only.** Rejected because configured evidence that cannot fail
   does not improve the verification gate.
