# Codex Packaging Runbook

Use this runbook when deciding how an adopting repository should expose dp to Codex.

## Recommendation

Start with the CLI, repository `AGENTS.md`, and the repo-local `dp-campaign-control` Codex skill.
Do not add MCP, a plugin, or new hooks unless the repository has a concrete need that the CLI and
skill cannot satisfy.

## Install or Inspect the Skill

The checked-in skill lives at:

```text
.agents/skills/dp-campaign-control/SKILL.md
```

Codex discovers repo-local skills from trusted projects. After adding or changing the skill, start
a new Codex session if the current session does not see it. The skill is safe to inspect because it
contains instructions only: no scripts, no MCP server configuration, no hooks, and no network
runtime.

Use the skill when an operator asks Codex to continue a dp campaign, recover a goal, route a
blocker, or complete a SPEC-80-style loop through dp.

## Default Agent Flow

```bash
dp doctor --json
dp campaign recover docs/campaigns/<campaign>.json --json
dp campaign run docs/campaigns/<campaign>.json --driver codex --supervised --managed --json
dp goal start docs/goals/<goal>.json --agent codex --json
dp evidence run docs/evidence/<evidence>.json --output docs/evidence-runs/<run>.json --json
dp verify --goal docs/goals/<goal>.json --evidence docs/evidence-runs/<run>.json --json
dp campaign sync-beads docs/campaigns/<campaign>.json --write --json
```

If blocked:

```bash
dp goal block docs/goals/<goal>.json --reason needs_decision --write-artifact --json
```

Use the route from the GoalContract: `needs_specification`, `needs_decision`, `needs_validator`,
`unsafe_scope`, or `budget_exhausted`.

## When to Consider MCP

Create a new ADR before adding MCP. The ADR must show:

1. Which agent experience is impossible or materially worse through CLI JSON.
2. Which commands or resources the MCP server exposes.
3. How command semantics stay identical to the CLI.
4. How trust, project scoping, timeouts, and failures are handled.
5. How tests prove the server does not become a hidden verification judge.

## When to Consider a Plugin

Create a new ADR before adding a plugin. A plugin is appropriate when dp needs to distribute a
stable bundle across teams or repositories, such as:

1. The campaign-control skill.
2. Reviewed hook examples.
3. Optional MCP configuration.
4. Supporting assets or app mappings.

Do not use plugin packaging as a substitute for stabilizing the underlying CLI protocol.

## Hook Boundary

Hooks remain optional, repo-local, and trust-gated. They may run cheap preflight checks such as:

```bash
dp codex preflight --event stop --json
```

They must not run LLM calls, broad evidence execution, `make check`, or completion verification.

