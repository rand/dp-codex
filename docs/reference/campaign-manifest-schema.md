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

Scaffold command:

```bash
dp campaign init --primary-spec docs/primary/example.md --write --json
```

Exit codes:

1. `0`: valid lint, successful status, or successful recovery.
2. `1`: invalid loaded manifest, or recovery found missing or invalid artifacts.
3. `2`: missing manifest file, malformed JSON, non-object JSON, unsupported schema, or unsupported
   command input.

Safety rules:

1. Campaign commands never call an LLM.
2. Campaign commands never execute evidence checks.
3. Campaign status is derived from linted artifacts and append-only goal events.
4. Recovery does not consult chat memory or hidden state.
5. A goal in `evidence_pending` is not treated as verified.
