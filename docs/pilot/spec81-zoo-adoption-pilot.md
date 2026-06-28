# SPEC-81 Zoo Adoption Pilot

Date: 2026-06-28

## Objective

Validate SPEC-81 adoption and agent-experience behavior against a representative non-dp repository.
The candidate was `/Users/rand/src/zoo`.

## Source Repo Inspection

The live zoo checkout was inspected read-only because it had unrelated local changes. No adoption
changes were applied there.

Observed state:

1. `git status --short --branch`: branch was `main...origin/main` with existing modified and
   untracked product files.
2. `dp adopt inspect --json`: classification `not_adopted`.
3. `dp instructions inspect --json`: discovered `README.md`; no `AGENTS.md`.
4. `dp instructions audit --json`: one warning, `instruction_missing_bootstrap`.
5. `dp agent bootstrap --json --detail brief`: returned a compact warning envelope with adoption
   state `not_adopted`.
6. `dp agent capabilities --json`: returned ToolCards successfully.

## Pilot Method

To avoid touching unrelated zoo work, the pilot used a temporary copy:

```bash
rsync -a --exclude .git --exclude .venv --exclude .uv-cache --exclude .pytest_cache \
  --exclude .hypothesis --exclude dist /Users/rand/src/zoo/ \
  /private/tmp/zoo-dp-pilot-fixed.DUaUih/
```

The pilot then ran:

```bash
dp adopt inspect --json
dp instructions audit --json
dp adopt plan --write --json
dp adopt apply docs/migrations/MIGRATION-2026-06-28-agent-experience.json --json
dp adopt apply docs/migrations/MIGRATION-2026-06-28-agent-experience.json --apply --json
dp adopt verify --json
dp agent bootstrap --json --detail brief
dp agent capabilities --json
dp skills audit --json
dp skills eval --json
dp hooks audit --json
dp hooks doctor --json
```

## Result

The first pilot run exposed a product gap: the adoption plan created event directories and skills,
but `dp adopt verify --json` still failed because no `dp-policy.json` existed. The adoption engine
was fixed so a missing policy is planned as an apply-mode, non-overwriting creation of:

```json
{
  "mode": "guided"
}
```

The fixed pilot then passed `dp adopt verify --json` with classification `legacy_dp`.

Applied artifacts in the temporary copy:

1. `dp-policy.json`
2. `.dp/goals/`
3. `.dp/campaigns/`
4. `.agents/skills/` with eight focused dp skills
5. `docs/migrations/MIGRATION-2026-06-28-agent-experience.json`
6. `docs/migrations/MIGRATION-2026-06-28-agent-experience.md`

AGENTS.md was not created. The plan kept it as a preview-only proposal.

## Friction

1. A dirty source checkout should not be adopted in place. The pilot used a temporary copy.
2. `dp doctor --json` in the adopted copy still reported `No .beads directory found`; adoption does
   not initialize Beads. This is correct for a conservative adoption layer, but it means a project
   that wants task-provider health must run an explicit Beads initialization step.
3. Instruction governance reported missing bootstrap guidance because no `AGENTS.md` existed and
   adoption correctly refused to create one automatically.

## Follow-Up

No new blocker was found after the minimal policy fix. A real adoption of zoo should be done in a
separate zoo-owned change, after its current local changes are either committed or intentionally
set aside.
