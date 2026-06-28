from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXPLAIN_SCHEMA_VERSION = "dp.explain.v1"


@dataclass(frozen=True)
class HintDefinition:
    code: str
    severity: str
    summary: str
    why_it_matters: str
    next_actions: tuple[dict[str, str], ...]
    docs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXPLAIN_SCHEMA_VERSION,
            "code": self.code,
            "severity": self.severity,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "next_actions": list(self.next_actions),
            "docs": list(self.docs),
        }


def explain_code(code: str) -> tuple[dict[str, Any], int]:
    normalized = code.strip()
    definition = HINTS.get(normalized) or ERROR_ALIASES.get(normalized)
    if definition is None:
        return (
            {
                "schema_version": EXPLAIN_SCHEMA_VERSION,
                "code": normalized,
                "severity": "warning",
                "summary": "No dp explanation is registered for this code.",
                "why_it_matters": (
                    "Agents should not guess repair behavior from an unknown code."
                ),
                "next_actions": [
                    {
                        "command": "dp agent bootstrap --json --detail brief",
                        "why": "Re-orient and choose a supported dp command surface.",
                    }
                ],
                "docs": ["docs/reference/hint-codes.md"],
            },
            1,
        )
    return definition.to_dict(), 0


def hint_payload(code: str) -> dict[str, str]:
    definition = HINTS.get(code) or ERROR_ALIASES.get(code)
    summary = definition.summary if definition is not None else "See dp explain for detail."
    severity = definition.severity if definition is not None else "warning"
    return {
        "code": code,
        "severity": severity,
        "message": summary,
        "explain_command": f"dp explain {code} --json",
    }


def registry_payload() -> dict[str, Any]:
    return {
        "schema_version": "dp.hints.v1",
        "codes": [definition.to_dict() for definition in HINTS.values()],
    }


def _action(command: str, why: str) -> dict[str, str]:
    return {"command": command, "why": why}


HINTS: dict[str, HintDefinition] = {
    "DP-HINT-BOOTSTRAP-RUN-DOCTOR": HintDefinition(
        code="DP-HINT-BOOTSTRAP-RUN-DOCTOR",
        severity="info",
        summary="Run dp doctor when bootstrap reports workflow health is unknown.",
        why_it_matters="Doctor checks whether the local task substrate is usable.",
        next_actions=(_action("dp doctor --json", "Check Beads and local workflow health."),),
        docs=("docs/runbooks/agent-session-bootstrap.md",),
    ),
    "DP-HINT-INSTRUCTIONS-FOUND": HintDefinition(
        code="DP-HINT-INSTRUCTIONS-FOUND",
        severity="info",
        summary="Local instruction files were found and should be treated as project law.",
        why_it_matters="dp hints do not supersede repository instructions.",
        next_actions=(
            _action("dp instructions audit --json", "Check instructions for conflicts."),
        ),
        docs=("docs/reference/instruction-governance.md",),
    ),
    "DP-HINT-INSTRUCTIONS-CONFLICT": HintDefinition(
        code="DP-HINT-INSTRUCTIONS-CONFLICT",
        severity="warning",
        summary="Instruction files contain potentially conflicting workflow guidance.",
        why_it_matters="Agents need a deterministic precedence decision before editing.",
        next_actions=(
            _action(
                "dp instructions plan-update --json",
                "Produce a reviewable update plan without mutating instructions.",
            ),
        ),
        docs=("docs/reference/instruction-governance.md",),
    ),
    "DP-HINT-INSTRUCTIONS-TOO-LARGE": HintDefinition(
        code="DP-HINT-INSTRUCTIONS-TOO-LARGE",
        severity="warning",
        summary="An instruction file is large enough to pressure an agent context window.",
        why_it_matters="Large instructions can crowd out task context and increase mistakes.",
        next_actions=(
            _action("dp instructions inspect --json", "Review instruction file sizes."),
        ),
        docs=("docs/reference/instruction-governance.md",),
    ),
    "DP-HINT-ADOPTION-AVAILABLE": HintDefinition(
        code="DP-HINT-ADOPTION-AVAILABLE",
        severity="info",
        summary="The repository can adopt more of the dp agent workflow.",
        why_it_matters="Adoption should be explicit and additive, not implicit mutation.",
        next_actions=(_action("dp adopt plan --write --json", "Write a reviewable plan."),),
        docs=("docs/reference/adoption-workflow.md",),
    ),
    "DP-HINT-ADOPTION-PLAN-REQUIRED": HintDefinition(
        code="DP-HINT-ADOPTION-PLAN-REQUIRED",
        severity="warning",
        summary="Adoption changes require an inspect and plan step before applying.",
        why_it_matters="Old project artifacts and instructions must be preserved.",
        next_actions=(_action("dp adopt inspect --json", "Inspect before planning changes."),),
        docs=("docs/reference/adoption-workflow.md",),
    ),
    "DP-HINT-MIGRATION-LEGACY-ARTIFACTS": HintDefinition(
        code="DP-HINT-MIGRATION-LEGACY-ARTIFACTS",
        severity="warning",
        summary="Legacy dp artifacts were found and need an additive migration plan.",
        why_it_matters="Legacy files may still encode project history or gates.",
        next_actions=(_action("dp adopt plan --write --json", "Record a migration plan."),),
        docs=("docs/runbooks/adopting-dp-in-existing-project.md",),
    ),
    "DP-HINT-GOAL-NOT-STARTED": HintDefinition(
        code="DP-HINT-GOAL-NOT-STARTED",
        severity="info",
        summary="A goal is ready or claimed but not yet started.",
        why_it_matters="Starting a goal records active work in the append-only event log.",
        next_actions=(
            _action("dp goal start <goal.json> --agent codex --json", "Record active work."),
        ),
        docs=("docs/reference/goal-state-machine.md",),
    ),
    "DP-HINT-GOAL-LEASE-STALE": HintDefinition(
        code="DP-HINT-GOAL-LEASE-STALE",
        severity="warning",
        summary="A goal lease is stale and must be released or reclaimed explicitly.",
        why_it_matters="dp should not claim over stale state without a visible decision.",
        next_actions=(
            _action("dp goal release <goal.json> --reason '<reason>' --json", "Release state."),
        ),
        docs=("docs/reference/goal-state-machine.md",),
    ),
    "DP-HINT-EVIDENCE-MISSING": HintDefinition(
        code="DP-HINT-EVIDENCE-MISSING",
        severity="error",
        summary="The goal references evidence that is missing or cannot be verified.",
        why_it_matters="Verification cannot advance without an external evidence artifact.",
        next_actions=(
            _action(
                "dp goal block <goal.json> --reason needs_validator --write-artifact --json",
                "Route the missing validator into a durable artifact.",
            ),
        ),
        docs=("docs/reference/evidence-plan-schema.md",),
    ),
    "DP-HINT-EVIDENCE-RUN-STALE": HintDefinition(
        code="DP-HINT-EVIDENCE-RUN-STALE",
        severity="warning",
        summary="The evidence run no longer matches the current evidence plan.",
        why_it_matters="Stale evidence is not proof for the current goal contract.",
        next_actions=(
            _action("dp evidence run <evidence.json> --json", "Regenerate evidence."),
        ),
        docs=("docs/reference/evidence-plan-schema.md",),
    ),
    "DP-HINT-EVIDENCE-FAILED": HintDefinition(
        code="DP-HINT-EVIDENCE-FAILED",
        severity="error",
        summary="A registered evidence check failed.",
        why_it_matters="Gates must be deterministic, and failed evidence blocks completion.",
        next_actions=(
            _action(
                "dp evidence run <evidence.json> --json --detail full",
                "Inspect the failing check output.",
            ),
        ),
        docs=("docs/runbooks/debugging-agent-handoffs.md",),
    ),
    "DP-HINT-CAMPAIGN-DRAFT": HintDefinition(
        code="DP-HINT-CAMPAIGN-DRAFT",
        severity="warning",
        summary="The campaign is still draft and cannot be used for execution handoff.",
        why_it_matters="Draft authoring artifacts must pass deterministic readiness gates.",
        next_actions=(
            _action("dp campaign ready <campaign.json> --write --json", "Promote if valid."),
        ),
        docs=("docs/reference/campaign-ready.md",),
    ),
    "DP-HINT-LOOP-NO-READY-NODES": HintDefinition(
        code="DP-HINT-LOOP-NO-READY-NODES",
        severity="warning",
        summary="The loop has no ready unclaimed nodes.",
        why_it_matters="The agent should resolve blockers, verify evidence, or stop cleanly.",
        next_actions=(
            _action("dp campaign status <campaign.json> --json --detail normal", "Recover state."),
        ),
        docs=("docs/reference/loop-ledger-schema.md",),
    ),
    "DP-HINT-BLOCKER-NEEDS-ADR": HintDefinition(
        code="DP-HINT-BLOCKER-NEEDS-ADR",
        severity="warning",
        summary="The blocker needs an ADR before implementation can proceed.",
        why_it_matters="Decision gaps should become durable project artifacts.",
        next_actions=(_action("dp adr create '<title>' --json", "Create an ADR."),),
        docs=("docs/runbooks/adr-workflow.md",),
    ),
    "DP-HINT-BLOCKER-NEEDS-SPEC": HintDefinition(
        code="DP-HINT-BLOCKER-NEEDS-SPEC",
        severity="warning",
        summary="The blocker needs a specification before implementation can proceed.",
        why_it_matters="Specification gaps should not be hidden in chat state.",
        next_actions=(
            _action(
                "dp goal block <goal.json> --reason needs_specification --write-artifact --json",
                "Create a spec route.",
            ),
        ),
        docs=("docs/reference/goal-contract-schema.md",),
    ),
    "DP-HINT-BLOCKER-NEEDS-VALIDATOR": HintDefinition(
        code="DP-HINT-BLOCKER-NEEDS-VALIDATOR",
        severity="warning",
        summary="The blocker needs a validator or evidence plan.",
        why_it_matters="Completion needs deterministic evidence, not narration.",
        next_actions=(
            _action(
                "dp goal block <goal.json> --reason needs_validator --write-artifact --json",
                "Create an evidence route.",
            ),
        ),
        docs=("docs/reference/evidence-plan-schema.md",),
    ),
    "DP-HINT-HOOKS-UNTRUSTED": HintDefinition(
        code="DP-HINT-HOOKS-UNTRUSTED",
        severity="warning",
        summary="Hook behavior is not yet audited.",
        why_it_matters="Hooks can steer agents but must not replace deterministic gates.",
        next_actions=(_action("dp hooks audit --json", "Audit local hook behavior."),),
        docs=("docs/reference/hook-governance.md",),
    ),
    "DP-HINT-HOOK-BYPASSED": HintDefinition(
        code="DP-HINT-HOOK-BYPASSED",
        severity="warning",
        summary="A hook or gate bypass path was detected.",
        why_it_matters="Bypasses require explicit rationale and follow-up verification.",
        next_actions=(_action("dp doctor --json", "Check repository workflow health."),),
        docs=("docs/runbooks/enforcement-workflow.md",),
    ),
    "DP-HINT-SKILL-SUGGESTED": HintDefinition(
        code="DP-HINT-SKILL-SUGGESTED",
        severity="info",
        summary="A focused dp skill matches the current agent task.",
        why_it_matters="Narrow skills can reduce prompt load without overriding AGENTS.md.",
        next_actions=(_action("dp skills eval --json", "Review deterministic trigger matches."),),
        docs=("docs/reference/skills.md",),
    ),
    "DP-HINT-SKILL-TRIGGER-AMBIGUOUS": HintDefinition(
        code="DP-HINT-SKILL-TRIGGER-AMBIGUOUS",
        severity="warning",
        summary="A prompt matched multiple skills or no clear workflow skill.",
        why_it_matters="Ambiguous triggers can cause agents to choose broad workflows.",
        next_actions=(_action("dp agent bootstrap --json --detail brief", "Re-orient first."),),
        docs=("docs/reference/skills.md",),
    ),
    "DP-HINT-TOKEN-BUDGET-TRUNCATED": HintDefinition(
        code="DP-HINT-TOKEN-BUDGET-TRUNCATED",
        severity="info",
        summary="The response omitted detail to stay within an agent budget.",
        why_it_matters=(
            "Compact output preserves context while expansion commands keep detail available."
        ),
        next_actions=(
            _action("<same command> --detail full", "Fetch full diagnostics when needed."),
        ),
        docs=("docs/reference/agent-response-contract.md",),
    ),
}


ERROR_ALIASES: dict[str, HintDefinition] = {
    "missing_evidence_path": HINTS["DP-HINT-EVIDENCE-MISSING"],
    "missing_goal_evidence_plan": HINTS["DP-HINT-EVIDENCE-MISSING"],
    "stale_evidence_plan": HINTS["DP-HINT-EVIDENCE-RUN-STALE"],
    "evidence_run_failed": HINTS["DP-HINT-EVIDENCE-FAILED"],
    "evidence_checks_failed": HINTS["DP-HINT-EVIDENCE-FAILED"],
    "campaign_not_ready": HINTS["DP-HINT-CAMPAIGN-DRAFT"],
    "no_ready_goal": HINTS["DP-HINT-LOOP-NO-READY-NODES"],
    "goal_already_claimed": HINTS["DP-HINT-GOAL-NOT-STARTED"],
}
