# Campaign Manifest Schema

CampaignManifest schema version `0.1` indexes the repository artifacts that make a campaign
recoverable across Codex sessions. It is project-general: the paths point at the adopting
repository's own primary spec, goals, evidence plans, loops, and supporting artifacts.

Required top-level fields:

1. `schema_version`: currently `0.1`.
2. `id`: stable campaign id such as `CAMPAIGN-waveguide`.
3. `title`: non-empty human title.
4. `primary_spec`: object containing `path`.
5. `artifacts`: object containing at least `goals` and `loops`.
6. `state`: object containing `status` and `current_loop`.

Required artifact fields:

1. `artifacts.goals`: non-empty list of sane relative paths to valid GoalContracts.
2. `artifacts.loops`: non-empty list of sane relative paths to valid LoopLedgers.

Optional artifact fields:

1. `artifacts.specs`: sane relative paths to supporting specs.
2. `artifacts.adrs`: sane relative paths to ADRs.
3. `artifacts.evidence_plans`: sane relative paths to valid EvidencePlans.
4. `artifacts.beads_epics`: Beads epic ids.
5. `artifacts.beads_issues`: Beads issue ids.

Generated campaign manifests may also include a `compiler` object. For `dp campaign init`, this is
deterministic provenance describing primary-spec signal extraction; it is not a readiness decision.

State fields:

1. `state.status`: one of `draft`, `ready`, `active`, `blocked`, `verified`, or `abandoned`.
2. `state.current_loop`: id of a declared loop ledger.
3. `state.current_goal`: optional GoalContract id.

Validation command:

```bash
dp campaign lint <campaign.json> --json
```

Status and recovery commands:

```bash
dp campaign status <campaign.json> --json
dp campaign recover <campaign.json> --json
```

Both commands include:

1. `events`: summary of `.dp/campaigns/events.jsonl` for the campaign.
2. `resume`: deterministic next-action package derived from the current loop and event logs.
   Goal-scoped resume packages include concrete evidence artifact commands where the GoalContract
   or loop node declares an EvidencePlan.

Resume actions:

1. `resume_claimed_goal`: continue an active non-stale claim.
2. `verify_evidence`: verify a goal with recorded evidence pending.
3. `resolve_blocker`: resolve a blocked goal before moving dependent work.
4. `claim_next_goal`: run the supervised handoff command to claim ready work.
5. `campaign_verified`: all current-loop goals are verified.
6. `no_ready_work`: no active, blocked, evidence-pending, ready, or verified action is available.

Supervised handoff command:

```bash
dp campaign run <campaign.json> --driver codex --supervised --json
```

`run` validates campaign state, resolves `state.current_loop`, and uses the same resume decision as
`recover`. If a current-loop goal is already actively claimed, `run` returns that resume package
without a new claim. Otherwise it claims one ready goal through the LoopLedger protocol, appends a
campaign `handoff_claimed` event under `.dp/campaigns/events.jsonl`, emits a Codex handoff package,
and stops. It does not launch an agent, execute evidence, or mark a campaign or goal verified.

Beads synchronization command:

```bash
dp campaign sync-beads <campaign.json> --json
dp campaign sync-beads <campaign.json> --write --json
```

`sync-beads` reconciles the current LoopLedger and append-only goal events with Beads. Dry-run mode
plans missing dependency edges and lifecycle updates without mutation. `--write` applies missing
`bd dep add`, `bd update`, and `bd close` operations explicitly. Beads status is not proof of
completion; verified state still comes from dp evidence-backed goal events.

Scaffold command:

```bash
dp campaign init --primary-spec docs/primary/example.md --write --json
```

Refinement command:

```bash
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --write --create-beads --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --llm --json
dp campaign refine docs/campaigns/CAMPAIGN-example.json --llm-response response.json --write --json
```

Exit codes:

1. `0`: valid lint, successful status/recovery, or prepared supervised run handoff.
2. `1`: invalid loaded manifest, recovery found missing or invalid artifacts, or no ready run handoff.
3. `2`: missing manifest file, malformed JSON, non-object JSON, unsupported schema, or unsupported
   command input.

Safety rules:

1. Campaign lint/status/recover never call an LLM.
2. `dp campaign refine --llm` is explicit authoring: dp emits a request and imports a response
   artifact; the calling agent performs any model/network call.
3. Campaign commands never execute evidence checks.
4. `dp campaign run` claims at most one ready goal and remains a supervised single-step adapter.
5. Campaign status is derived from linted artifacts and append-only goal events.
6. Recovery does not consult chat memory or hidden state.
7. A goal in `evidence_pending` is not treated as verified.
8. Refinement authoring preserves `draft` status until deterministic readiness gates exist.
9. Beads epics/issues are materialized only through explicit write flags.
10. Campaign events are progress records, not proof of behavioral completion.
11. Beads lifecycle synchronization is explicit reconciliation, not hidden goal-command mutation.
