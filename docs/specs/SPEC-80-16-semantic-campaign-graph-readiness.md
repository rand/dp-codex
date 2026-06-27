# SPEC-80.16 Semantic Campaign Graph Readiness

Status: active
Issue: dpcx-pb5.13
Parent: SPEC-80

[SPEC-80.16]

## Intent

SPEC-80 campaigns now have draft scaffolding, deterministic refinement, agent-mediated LLM
refinement imports, loop scheduling, recovery, evidence execution, goal verification, blocker
routing, and Beads reconciliation. The missing gate is the promotion boundary between an authored
campaign graph and an executable campaign graph.

This slice adds deterministic campaign readiness promotion. It prevents heading-derived scaffold
nodes, unresolved LLM authoring metadata, missing validators, missing child specs, or incomplete
Beads linkage from being treated as ready work.

## Command

```bash
dp campaign ready <campaign.json> --json
dp campaign ready <campaign.json> --write --json
```

Dry-run mode writes nothing. Write mode promotes `state.status` from `draft` to `ready` only when
all deterministic readiness gates pass. A campaign already in `ready` is accepted idempotently and
may receive refreshed readiness metadata when `--write` is supplied.

## Requirements

1. `dp campaign ready` MUST lint the CampaignManifest before any readiness decision.
2. The command MUST reject malformed input with exit code `2`, invalid loaded campaign artifacts
   with exit code `1`, and successful readiness with exit code `0`.
3. The command MUST NOT call an LLM.
4. The command MUST NOT execute EvidencePlan checks.
5. The command MUST NOT mutate Beads.
6. The command MUST NOT write unless `--write` is supplied and all readiness gates pass.
7. `--write` MUST refuse to promote campaigns whose `state.status` is not `draft` or `ready`.
8. Every declared LoopLedger MUST lint successfully and remain acyclic through `dp loop lint`.
9. Every current-loop node MUST declare `goal_path`, `goal_id`, `evidence_plan`, and
   `beads_issue_id`.
10. Every node EvidencePlan MUST be declared in the CampaignManifest and MUST link to the same
    `goal_id` as the node.
11. Every node GoalContract MUST link to the same EvidencePlan path used by the loop node.
12. Every node MUST have child-spec coverage through either `goal.refinement.spec_path` or
    `goal.source.path`, and that spec path MUST exist and be declared in `artifacts.specs`.
13. A decision node MUST have an ADR path when its compiler/refinement metadata still carries
    decision classification or routes. The ADR MUST exist and be declared in `artifacts.adrs`.
14. A campaign MUST fail readiness when any campaign, goal, evidence, or compiler metadata still
    contains unresolved blocker states: `needs_refinement`, `needs_specification`,
    `needs_decision`, `needs_validator`, `draft_placeholder`, or `blocked`.
15. LLM-authored dependency metadata MUST be back-pressured into deterministic loop edges before
    readiness. If a goal refinement contains `llm.dependencies`, each dependency MUST resolve to
    a known loop node id, goal id, or artifact path and MUST be represented in `depends_on` where it
    names another node or goal.
16. The readiness result MUST include stable checks, structured errors, structured warnings,
    readiness metadata, and whether a write occurred.
17. Write-mode metadata MUST record deterministic provenance, no network calls, and input artifact
    hashes.
18. Supervised campaign handoff commands MUST refuse draft CampaignManifests instead of treating
    authoring drafts as executable campaigns.

## Readiness Gate Table

| Gate | Authority | Failure code |
| --- | --- | --- |
| CampaignManifest lint passes | `dp campaign lint` | `campaign_lint_failed` |
| Campaign status is promotable | manifest `state.status` | `campaign_state_not_promotable` |
| Loop ledgers lint and are acyclic | `dp loop lint` | `loop_lint_failed` |
| Node evidence exists and matches goal | LoopLedger + EvidencePlan | `node_evidence_mismatch` |
| Goal evidence path matches node | GoalContract + LoopLedger | `goal_evidence_mismatch` |
| Node has child-spec coverage | GoalContract + artifacts | `missing_child_spec` |
| Decision nodes have ADR coverage | refinement/compiler metadata + artifacts | `missing_decision_adr` |
| No unresolved refinement markers remain | campaign/goal/evidence metadata | `unresolved_refinement_state` |
| LLM dependency hints are resolved as graph edges | GoalContract refinement metadata + LoopLedger | `llm_dependency_not_materialized` |
| Beads issue links exist per node | LoopLedger | `missing_beads_issue` |

## Output Shape

Example failure:

```json
{
  "ok": false,
  "command": "campaign.ready",
  "campaign_id": "CAMPAIGN-example",
  "write": false,
  "written": false,
  "ready": false,
  "checks": [
    {"name": "campaign_lint", "ok": true},
    {"name": "graph_readiness", "ok": false}
  ],
  "errors": [
    {
      "code": "missing_child_spec",
      "path": "$.artifacts.loops[0].nodes[0]",
      "message": "Loop node must have a declared child spec before campaign readiness."
    }
  ],
  "warnings": []
}
```

Example success:

```json
{
  "ok": true,
  "command": "campaign.ready",
  "campaign_id": "CAMPAIGN-example",
  "write": true,
  "written": true,
  "ready": true,
  "state": {"before": "draft", "after": "ready"},
  "readiness": {
    "mode": "deterministic_campaign_ready",
    "network_calls": false,
    "llm_judgment": false,
    "provenance": {
      "kind": "deterministic_campaign_ready",
      "input_artifact_hashes": {}
    }
  },
  "checks": [
    {"name": "campaign_lint", "ok": true},
    {"name": "graph_readiness", "ok": true}
  ],
  "errors": [],
  "warnings": []
}
```

## Formal Invariants

Let `C` be a CampaignManifest, `L` its declared loop ledgers, `G` its declared GoalContracts,
`E` its declared EvidencePlans, and `R(C, L, G, E)` the readiness predicate.

1. Gate purity:
   `R` performs no network calls, model calls, Beads writes, evidence execution, or shell command
   execution.
2. Write safety:
   if `R = false`, file writes performed by `dp campaign ready --write` equal zero.
3. Promotion equivalence:
   `dp campaign ready C --write` sets `C.state.status = ready` if and only if
   `dp campaign ready C` would return `ready = true`.
4. Artifact closure:
   every executable loop node in a ready campaign has a declared GoalContract, EvidencePlan,
   child spec, and Beads issue id.
5. Evidence alignment:
   for every ready node `n`, `n.goal_id = EvidencePlan(n.evidence_plan).goal_id` and
   `GoalContract(n.goal_path).evidence.evidence_plan = n.evidence_plan`.
6. Dependency materialization:
   LLM dependency hints may inform authoring, but a ready graph's executable dependency truth is
   the LoopLedger `depends_on` relation.
7. No unresolved blockers:
   a ready campaign contains no `needs_*`, `blocked`, or placeholder refinement states in its
   campaign, goal, or evidence metadata.

## Non-Goals

1. No primary-spec semantic planning beyond existing scaffold/refine metadata.
2. No LLM refinement call.
3. No evidence execution.
4. No autonomous runner.
5. No Beads mutation.
6. No automatic conversion of ambiguous prose dependency cues into loop edges.

## Verification

Required checks:

```bash
pytest tests/test_campaign_readiness.py tests/unit/test_output_schemas.py
make check
dp trace validate --json
dp trace coverage --json
dp verify --json
```
