from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO, cast

from dp.core.adoption import apply_adoption, inspect_adoption, plan_adoption, verify_adoption
from dp.core.adr import create_adr, list_adrs, show_adr, update_adr_status
from dp.core.agent_experience import (
    agent_bootstrap,
    agent_capabilities,
    agent_eval,
    wrap_progressive_payload,
)
from dp.core.agent_launch import launch_agent_goal
from dp.core.campaign_beads_sync import sync_campaign_beads
from dp.core.campaign_init import init_campaign_from_primary_spec
from dp.core.campaign_manifest import (
    campaign_recover,
    campaign_status,
    lint_campaign_file,
)
from dp.core.campaign_readiness import ready_campaign
from dp.core.campaign_refine import refine_campaign
from dp.core.campaign_run import run_campaign_once
from dp.core.codex_preflight import run_codex_preflight
from dp.core.coverage import compute_trace_coverage
from dp.core.decompose import decompose_items, resolve_context_window
from dp.core.evidence_lint import lint_evidence_file
from dp.core.evidence_run import run_evidence_file
from dp.core.goal_emit import emit_goal_prompt
from dp.core.goal_lint import lint_goal_file
from dp.core.goal_state import (
    block_goal,
    claim_goal,
    complete_goal,
    goal_status,
    heartbeat_goal,
    release_goal,
    start_goal,
    verify_goal,
)
from dp.core.goal_verification import verify_goal_orchestrated
from dp.core.hints import explain_code
from dp.core.hooks import audit_hooks, doctor_hooks, scaffold_hooks
from dp.core.instructions import audit_instructions, inspect_instructions, plan_instruction_update
from dp.core.loop_ledger import lint_loop_file, loop_next, loop_status
from dp.core.policy import load_policy_config
from dp.core.progress import (
    ProgressReport,
    collect_progress_snapshot,
    evaluate_watch_triggers,
    load_snapshot,
    write_progress_report,
)
from dp.core.review import run_review
from dp.core.skills import audit_skills, eval_skills, lint_skills, scaffold_skills
from dp.core.spec_parser import parse_spec_ids
from dp.core.task_normalization import normalize_priority, normalize_status
from dp.core.trace_parser import parse_trace_markers, parse_trace_references
from dp.core.validation import validate_trace_references
from dp.core.verify import run_goal_backward_verify
from dp.enforcement import run_enforcement
from dp.providers.beads import (
    BdUnavailableError,
    BeadsNotInitializedError,
    check_beads_health,
    run_bd,
)

DEFAULT_SPEC_GLOBS = ("docs/specs/**/*.md", "docs/**/*.md")
DEFAULT_TRACE_GLOBS = ("dp/**/*.py", "tests/**/*.py")
DEFAULT_ADR_DIRECTORY = Path("docs/adr")
DEFAULT_VERIFY_MANIFEST = Path("docs/verify/manifest.json")
DEFAULT_POLICY_PATH = Path("dp-policy.json")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = cast(Callable[[argparse.Namespace], int], args.handler)
    return handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    trace_parser = subparsers.add_parser("trace")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_command", required=True)

    coverage_parser = trace_subparsers.add_parser(
        "coverage",
        help="Report trace coverage for SPEC IDs.",
    )
    coverage_parser.add_argument(
        "--spec-glob",
        action="append",
        dest="spec_globs",
        help="Glob for spec documents containing [SPEC-XX.YY]. Repeatable.",
    )
    coverage_parser.add_argument(
        "--trace-glob",
        action="append",
        dest="trace_globs",
        help="Glob for files containing @trace SPEC-XX.YY markers. Repeatable.",
    )
    coverage_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    coverage_parser.set_defaults(handler=_run_trace_coverage)

    validate_parser = trace_subparsers.add_parser(
        "validate",
        help="Validate trace references against defined SPEC IDs.",
    )
    validate_parser.add_argument(
        "--spec-glob",
        action="append",
        dest="spec_globs",
        help="Glob for spec documents containing [SPEC-XX.YY]. Repeatable.",
    )
    validate_parser.add_argument(
        "--trace-glob",
        action="append",
        dest="trace_globs",
        help="Glob for files containing @trace SPEC-XX.YY markers. Repeatable.",
    )
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    validate_parser.set_defaults(handler=_run_trace_validate)

    decompose_parser = subparsers.add_parser(
        "decompose",
        help="Generate DAG decomposition plan with context-window controls.",
    )
    decompose_parser.add_argument("--item", action="append", dest="items")
    decompose_parser.add_argument("--spec-glob", action="append", dest="spec_globs")
    decompose_parser.add_argument("--context-window", type=int)
    decompose_parser.add_argument(
        "--preset",
        choices=["codex-small", "codex-medium", "codex-large"],
    )
    decompose_parser.add_argument("--json", action="store_true")
    decompose_parser.set_defaults(handler=_run_decompose)

    progress_parser = subparsers.add_parser(
        "progress",
        help="Generate markdown/json progress snapshots and optional watch trigger evaluation.",
    )
    progress_parser.add_argument("--output-dir", default="docs/progress")
    progress_parser.add_argument("--watch", action="store_true")
    progress_parser.add_argument("--previous")
    progress_parser.add_argument("--json", action="store_true")
    progress_parser.set_defaults(handler=_run_progress)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check local dp-codex workflow health without mutating state.",
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.add_argument("--detail", choices=["brief", "normal", "full"])
    doctor_parser.set_defaults(handler=_run_doctor)

    explain_parser = subparsers.add_parser(
        "explain",
        help="Explain a stable dp hint or error code.",
    )
    explain_parser.add_argument("code")
    explain_parser.add_argument("--json", action="store_true")
    explain_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    explain_parser.set_defaults(handler=_run_explain)

    codex_parser = subparsers.add_parser("codex")
    codex_subparsers = codex_parser.add_subparsers(dest="codex_command", required=True)

    codex_preflight_parser = codex_subparsers.add_parser(
        "preflight",
        help="Run cheap deterministic checks for Codex session hooks.",
    )
    codex_preflight_parser.add_argument("--event", required=True)
    codex_preflight_parser.add_argument("--strict", action="store_true")
    codex_preflight_parser.add_argument("--json", action="store_true")
    codex_preflight_parser.set_defaults(handler=_run_codex_preflight)

    goal_parser = subparsers.add_parser("goal")
    goal_subparsers = goal_parser.add_subparsers(dest="goal_command", required=True)

    goal_lint_parser = goal_subparsers.add_parser(
        "lint",
        help="Validate a GoalContract without model calls or side effects.",
    )
    goal_lint_parser.add_argument("goal")
    goal_lint_parser.add_argument("--json", action="store_true")
    goal_lint_parser.set_defaults(handler=_run_goal_lint)

    goal_status_parser = goal_subparsers.add_parser(
        "status",
        help="Reconstruct goal lifecycle state from append-only events.",
    )
    goal_status_parser.add_argument("goal")
    goal_status_parser.add_argument("--json", action="store_true")
    goal_status_parser.add_argument("--detail", choices=["brief", "normal", "full"])
    goal_status_parser.set_defaults(handler=_run_goal_status)

    goal_claim_parser = goal_subparsers.add_parser(
        "claim",
        help="Claim a valid goal with a finite lease.",
    )
    goal_claim_parser.add_argument("goal")
    goal_claim_parser.add_argument("--agent", required=True)
    goal_claim_parser.add_argument("--lease", default="2h")
    goal_claim_parser.add_argument("--json", action="store_true")
    goal_claim_parser.set_defaults(handler=_run_goal_claim)

    goal_start_parser = goal_subparsers.add_parser(
        "start",
        help="Record that an agent started a valid goal.",
    )
    goal_start_parser.add_argument("goal")
    goal_start_parser.add_argument("--agent", required=True)
    goal_start_parser.add_argument("--json", action="store_true")
    goal_start_parser.set_defaults(handler=_run_goal_start)

    goal_heartbeat_parser = goal_subparsers.add_parser(
        "heartbeat",
        help="Record a heartbeat for the active goal claim.",
    )
    goal_heartbeat_parser.add_argument("goal")
    goal_heartbeat_parser.add_argument("--json", action="store_true")
    goal_heartbeat_parser.set_defaults(handler=_run_goal_heartbeat)

    goal_block_parser = goal_subparsers.add_parser(
        "block",
        help="Record a structured blocker for a goal.",
    )
    goal_block_parser.add_argument("goal")
    goal_block_parser.add_argument("--reason", required=True)
    goal_block_parser.add_argument("--write-artifact", action="store_true")
    goal_block_parser.add_argument("--json", action="store_true")
    goal_block_parser.set_defaults(handler=_run_goal_block)

    goal_release_parser = goal_subparsers.add_parser(
        "release",
        help="Release a goal claim with a reason.",
    )
    goal_release_parser.add_argument("goal")
    goal_release_parser.add_argument("--reason", required=True)
    goal_release_parser.add_argument("--json", action="store_true")
    goal_release_parser.set_defaults(handler=_run_goal_release)

    goal_complete_parser = goal_subparsers.add_parser(
        "complete",
        help="Record evidence for a goal without declaring behavioral verification.",
    )
    goal_complete_parser.add_argument("goal")
    goal_complete_parser.add_argument("--evidence", required=True)
    goal_complete_parser.add_argument("--json", action="store_true")
    goal_complete_parser.set_defaults(handler=_run_goal_complete)

    goal_verify_parser = goal_subparsers.add_parser(
        "verify",
        help="Verify a goal from a matching successful dp evidence run artifact.",
    )
    goal_verify_parser.add_argument("goal")
    goal_verify_parser.add_argument("--evidence", required=True)
    goal_verify_parser.add_argument("--json", action="store_true")
    goal_verify_parser.add_argument("--detail", choices=["brief", "normal", "full"])
    goal_verify_parser.set_defaults(handler=_run_goal_verify)

    goal_emit_parser = goal_subparsers.add_parser(
        "emit",
        help="Emit an agent-operable goal prompt from a valid contract.",
    )
    goal_emit_parser.add_argument("goal")
    goal_emit_parser.add_argument("--format", choices=["codex"], default="codex")
    goal_emit_parser.add_argument("--json", action="store_true")
    goal_emit_parser.set_defaults(handler=_run_goal_emit)

    adr_parser = subparsers.add_parser("adr")
    adr_subparsers = adr_parser.add_subparsers(dest="adr_command", required=True)

    adr_create_parser = adr_subparsers.add_parser("create", help="Create a new ADR document.")
    adr_create_parser.add_argument("title")
    adr_create_parser.add_argument("--status", default="proposal")
    adr_create_parser.add_argument("--json", action="store_true")
    adr_create_parser.set_defaults(handler=_run_adr_create)

    adr_list_parser = adr_subparsers.add_parser("list", help="List ADR documents.")
    adr_list_parser.add_argument("--json", action="store_true")
    adr_list_parser.set_defaults(handler=_run_adr_list)

    adr_show_parser = adr_subparsers.add_parser("show", help="Show ADR contents.")
    adr_show_parser.add_argument("identifier")
    adr_show_parser.add_argument("--json", action="store_true")
    adr_show_parser.set_defaults(handler=_run_adr_show)

    adr_update_parser = adr_subparsers.add_parser("update", help="Update ADR status.")
    adr_update_parser.add_argument("identifier")
    adr_update_parser.add_argument("--status", required=True)
    adr_update_parser.add_argument("--superseded-by")
    adr_update_parser.add_argument("--json", action="store_true")
    adr_update_parser.set_defaults(handler=_run_adr_update)

    review_parser = subparsers.add_parser(
        "review",
        help="Run deterministic checklist review and commit-readiness summary.",
    )
    review_parser.add_argument("--json", action="store_true")
    review_parser.set_defaults(handler=_run_review)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Run goal-backward verification across truths, artifacts, and links.",
    )
    verify_parser.add_argument("--manifest", default=DEFAULT_VERIFY_MANIFEST.as_posix())
    verify_parser.add_argument("--goal")
    verify_parser.add_argument("--evidence")
    verify_parser.add_argument("--evidence-output")
    verify_parser.add_argument("--force", action="store_true")
    verify_parser.add_argument("--json", action="store_true")
    verify_parser.set_defaults(handler=_run_verify)

    policy_parser = subparsers.add_parser(
        "policy",
        help="Validate and inspect enforcement policy configuration.",
    )
    policy_subparsers = policy_parser.add_subparsers(dest="policy_command", required=True)

    policy_validate_parser = policy_subparsers.add_parser(
        "validate",
        help="Validate policy schema and print effective checks.",
    )
    policy_validate_parser.add_argument("--config", default=DEFAULT_POLICY_PATH.as_posix())
    policy_validate_parser.add_argument("--json", action="store_true")
    policy_validate_parser.set_defaults(handler=_run_policy_validate)

    enforce_parser = subparsers.add_parser(
        "enforce",
        help="Run policy-controlled enforcement checks for hook/CI stages.",
    )
    enforce_subparsers = enforce_parser.add_subparsers(dest="enforce_command", required=True)

    for stage in ("pre-commit", "pre-push"):
        stage_parser = enforce_subparsers.add_parser(
            stage,
            help=f"Run enforcement checks for {stage}.",
        )
        stage_parser.add_argument(
            "--policy",
            default=DEFAULT_POLICY_PATH.as_posix(),
            help="Path to policy JSON file.",
        )
        stage_parser.add_argument("--json", action="store_true")
        stage_parser.set_defaults(handler=_run_enforce, stage=stage)

    task_parser = subparsers.add_parser("task")
    task_subparsers = task_parser.add_subparsers(dest="task_command", required=True)

    task_ready_parser = task_subparsers.add_parser(
        "ready",
        help="List ready issues from Beads.",
    )
    task_ready_parser.add_argument("--json", action="store_true")
    task_ready_parser.set_defaults(handler=_run_task_ready)

    task_claim_parser = task_subparsers.add_parser(
        "claim",
        help="Atomically claim ready or known Beads work and emit scoped intake context.",
    )
    task_claim_parser.add_argument("issue_id", nargs="?")
    task_claim_parser.add_argument("--json", action="store_true")
    task_claim_parser.set_defaults(handler=_run_task_claim)

    task_show_parser = task_subparsers.add_parser(
        "show",
        help="Show an issue from Beads.",
    )
    task_show_parser.add_argument("issue_id")
    task_show_parser.add_argument("--json", action="store_true")
    task_show_parser.set_defaults(handler=_run_task_show)

    task_update_parser = task_subparsers.add_parser(
        "update",
        help="Update issue status/priority/owner in Beads.",
    )
    task_update_parser.add_argument("issue_id")
    task_update_parser.add_argument("--status")
    task_update_parser.add_argument("--priority")
    task_update_parser.add_argument("--owner")
    task_update_parser.add_argument("--json", action="store_true")
    task_update_parser.set_defaults(handler=_run_task_update)

    task_discover_parser = task_subparsers.add_parser(
        "discover",
        help="Create discovered work linked to a source issue.",
    )
    task_discover_parser.add_argument("source_id")
    task_discover_parser.add_argument("title")
    task_discover_parser.add_argument("--description")
    task_discover_parser.add_argument("--acceptance")
    task_discover_parser.add_argument("--priority")
    task_discover_parser.add_argument("--labels")
    task_discover_parser.add_argument("--assignee")
    task_discover_parser.add_argument("--dry-run", action="store_true")
    task_discover_parser.add_argument("--json", action="store_true")
    task_discover_parser.set_defaults(handler=_run_task_discover)

    task_close_parser = task_subparsers.add_parser(
        "close",
        help="Close an issue in Beads.",
    )
    task_close_parser.add_argument("issue_id")
    task_close_parser.add_argument("--reason", required=True)
    task_close_parser.add_argument("--json", action="store_true")
    task_close_parser.set_defaults(handler=_run_task_close)

    agent_parser = subparsers.add_parser("agent")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    agent_bootstrap_parser = agent_subparsers.add_parser(
        "bootstrap",
        help="Orient an agent in the current dp-aware repository.",
    )
    agent_bootstrap_parser.add_argument("--json", action="store_true")
    agent_bootstrap_parser.add_argument(
        "--detail",
        choices=["brief", "normal", "full"],
        default="brief",
    )
    agent_bootstrap_parser.set_defaults(handler=_run_agent_bootstrap)

    agent_capabilities_parser = agent_subparsers.add_parser(
        "capabilities",
        help="Expose compact ToolCards for agent command discovery.",
    )
    agent_capabilities_parser.add_argument("--json", action="store_true")
    agent_capabilities_parser.set_defaults(handler=_run_agent_capabilities)

    agent_eval_parser = agent_subparsers.add_parser(
        "eval",
        help="Run lightweight deterministic agent-usability evals.",
    )
    agent_eval_parser.add_argument("--json", action="store_true")
    agent_eval_parser.set_defaults(handler=_run_agent_eval)

    agent_prompt_parser = agent_subparsers.add_parser(
        "prompt",
        help="Emit an agent prompt from a valid GoalContract.",
    )
    agent_prompt_parser.add_argument("--goal", required=True)
    agent_prompt_parser.add_argument("--format", choices=["codex"], default="codex")
    agent_prompt_parser.add_argument("--json", action="store_true")
    agent_prompt_parser.set_defaults(handler=_run_agent_prompt)

    agent_launch_parser = agent_subparsers.add_parser(
        "launch",
        help="Claim and start one goal, then emit a supervised agent handoff package.",
    )
    agent_launch_parser.add_argument("--goal", required=True)
    agent_launch_parser.add_argument("--driver", default="codex")
    agent_launch_parser.add_argument("--agent", default="codex")
    agent_launch_parser.add_argument("--lease", default="2h")
    agent_launch_parser.add_argument("--supervised", action="store_true")
    agent_launch_parser.add_argument("--json", action="store_true")
    agent_launch_parser.set_defaults(handler=_run_agent_launch)

    instructions_parser = subparsers.add_parser("instructions")
    instructions_subparsers = instructions_parser.add_subparsers(
        dest="instructions_command",
        required=True,
    )
    instructions_inspect_parser = instructions_subparsers.add_parser(
        "inspect",
        help="Discover instruction files and precedence without mutation.",
    )
    instructions_inspect_parser.add_argument("--json", action="store_true")
    instructions_inspect_parser.add_argument(
        "--detail",
        choices=["brief", "normal", "full"],
        default="normal",
    )
    instructions_inspect_parser.set_defaults(handler=_run_instructions_inspect)

    instructions_audit_parser = instructions_subparsers.add_parser(
        "audit",
        help="Audit instruction conflicts without mutation.",
    )
    instructions_audit_parser.add_argument("--json", action="store_true")
    instructions_audit_parser.set_defaults(handler=_run_instructions_audit)

    instructions_plan_parser = instructions_subparsers.add_parser(
        "plan-update",
        help="Preview a minimal instruction update plan without mutation.",
    )
    instructions_plan_parser.add_argument("--json", action="store_true")
    instructions_plan_parser.set_defaults(handler=_run_instructions_plan_update)

    adopt_parser = subparsers.add_parser("adopt")
    adopt_subparsers = adopt_parser.add_subparsers(dest="adopt_command", required=True)
    _add_adoption_subcommands(adopt_subparsers)

    migrate_parser = subparsers.add_parser("migrate")
    migrate_subparsers = migrate_parser.add_subparsers(dest="migrate_command", required=True)
    _add_adoption_subcommands(migrate_subparsers, handler_prefix="migrate")

    skills_parser = subparsers.add_parser("skills")
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command", required=True)
    skills_scaffold_parser = skills_subparsers.add_parser(
        "scaffold",
        help="Scaffold focused repo-scoped Codex skills.",
    )
    skills_scaffold_parser.add_argument("--target", choices=["repo"], required=True)
    skills_scaffold_parser.add_argument("--json", action="store_true")
    skills_scaffold_parser.set_defaults(handler=_run_skills_scaffold)

    skills_lint_parser = skills_subparsers.add_parser("lint", help="Lint repo-scoped skills.")
    skills_lint_parser.add_argument("--json", action="store_true")
    skills_lint_parser.set_defaults(handler=_run_skills_lint)

    skills_audit_parser = skills_subparsers.add_parser("audit", help="Audit repo-scoped skills.")
    skills_audit_parser.add_argument("--json", action="store_true")
    skills_audit_parser.set_defaults(handler=_run_skills_audit)

    skills_eval_parser = skills_subparsers.add_parser(
        "eval",
        help="Run deterministic skill trigger evals.",
    )
    skills_eval_parser.add_argument("--json", action="store_true")
    skills_eval_parser.set_defaults(handler=_run_skills_eval)

    hooks_parser = subparsers.add_parser("hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command", required=True)
    hooks_audit_parser = hooks_subparsers.add_parser("audit", help="Audit local hooks.")
    hooks_audit_parser.add_argument("--json", action="store_true")
    hooks_audit_parser.set_defaults(handler=_run_hooks_audit)

    hooks_doctor_parser = hooks_subparsers.add_parser("doctor", help="Summarize hook health.")
    hooks_doctor_parser.add_argument("--json", action="store_true")
    hooks_doctor_parser.set_defaults(handler=_run_hooks_doctor)

    hooks_scaffold_parser = hooks_subparsers.add_parser(
        "scaffold",
        help="Preview deterministic hook templates.",
    )
    hooks_scaffold_parser.add_argument("--target", choices=["git", "codex"], required=True)
    hooks_scaffold_parser.add_argument("--write", action="store_true")
    hooks_scaffold_parser.add_argument("--json", action="store_true")
    hooks_scaffold_parser.set_defaults(handler=_run_hooks_scaffold)

    evidence_parser = subparsers.add_parser("evidence")
    evidence_subparsers = evidence_parser.add_subparsers(
        dest="evidence_command",
        required=True,
    )

    evidence_lint_parser = evidence_subparsers.add_parser(
        "lint",
        help="Validate an EvidencePlan without executing checks.",
    )
    evidence_lint_parser.add_argument("evidence")
    evidence_lint_parser.add_argument("--json", action="store_true")
    evidence_lint_parser.set_defaults(handler=_run_evidence_lint)

    evidence_run_parser = evidence_subparsers.add_parser(
        "run",
        help="Run a linted EvidencePlan with registered argv checks and typed assertions.",
    )
    evidence_run_parser.add_argument("evidence")
    evidence_run_parser.add_argument("--output")
    evidence_run_parser.add_argument("--force", action="store_true")
    evidence_run_parser.add_argument("--json", action="store_true")
    evidence_run_parser.add_argument("--detail", choices=["brief", "normal", "full"])
    evidence_run_parser.set_defaults(handler=_run_evidence_run)

    loop_parser = subparsers.add_parser("loop")
    loop_subparsers = loop_parser.add_subparsers(
        dest="loop_command",
        required=True,
    )

    loop_lint_parser = loop_subparsers.add_parser(
        "lint",
        help="Validate a LoopLedger without model calls or side effects.",
    )
    loop_lint_parser.add_argument("loop")
    loop_lint_parser.add_argument("--json", action="store_true")
    loop_lint_parser.set_defaults(handler=_run_loop_lint)

    loop_status_parser = loop_subparsers.add_parser(
        "status",
        help="Reconstruct loop node state from GoalContracts and goal events.",
    )
    loop_status_parser.add_argument("loop")
    loop_status_parser.add_argument("--json", action="store_true")
    loop_status_parser.set_defaults(handler=_run_loop_status)

    loop_next_parser = loop_subparsers.add_parser(
        "next",
        help="Return the next ready unclaimed loop goal.",
    )
    loop_next_parser.add_argument("loop")
    loop_next_parser.add_argument("--claim", action="store_true")
    loop_next_parser.add_argument("--agent", default="codex")
    loop_next_parser.add_argument("--lease", default="2h")
    loop_next_parser.add_argument("--emit", choices=["codex"])
    loop_next_parser.add_argument("--json", action="store_true")
    loop_next_parser.add_argument("--detail", choices=["brief", "normal", "full"])
    loop_next_parser.set_defaults(handler=_run_loop_next)

    campaign_parser = subparsers.add_parser("campaign")
    campaign_subparsers = campaign_parser.add_subparsers(
        dest="campaign_command",
        required=True,
    )

    campaign_init_parser = campaign_subparsers.add_parser(
        "init",
        help="Create a conservative campaign scaffold from a local primary spec.",
    )
    campaign_init_parser.add_argument("--primary-spec", required=True)
    campaign_init_parser.add_argument("--write", action="store_true")
    campaign_init_parser.add_argument("--json", action="store_true")
    campaign_init_parser.set_defaults(handler=_run_campaign_init)

    campaign_lint_parser = campaign_subparsers.add_parser(
        "lint",
        help="Validate a CampaignManifest without executing campaign work.",
    )
    campaign_lint_parser.add_argument("campaign")
    campaign_lint_parser.add_argument("--json", action="store_true")
    campaign_lint_parser.set_defaults(handler=_run_campaign_lint)

    campaign_status_parser = campaign_subparsers.add_parser(
        "status",
        help="Reconstruct campaign state from manifest artifacts and goal events.",
    )
    campaign_status_parser.add_argument("campaign")
    campaign_status_parser.add_argument("--json", action="store_true")
    campaign_status_parser.add_argument("--detail", choices=["brief", "normal", "full"])
    campaign_status_parser.set_defaults(handler=_run_campaign_status)

    campaign_recover_parser = campaign_subparsers.add_parser(
        "recover",
        help="Report whether campaign state can be recovered without chat memory.",
    )
    campaign_recover_parser.add_argument("campaign")
    campaign_recover_parser.add_argument("--json", action="store_true")
    campaign_recover_parser.set_defaults(handler=_run_campaign_recover)

    campaign_ready_parser = campaign_subparsers.add_parser(
        "ready",
        help="Promote a draft campaign to ready when deterministic graph gates pass.",
    )
    campaign_ready_parser.add_argument("campaign")
    campaign_ready_parser.add_argument("--write", action="store_true")
    campaign_ready_parser.add_argument("--json", action="store_true")
    campaign_ready_parser.set_defaults(handler=_run_campaign_ready)

    campaign_refine_parser = campaign_subparsers.add_parser(
        "refine",
        help="Refine a draft campaign into authoring artifacts and optional Beads work.",
    )
    campaign_refine_parser.add_argument("campaign")
    campaign_refine_parser.add_argument("--write", action="store_true")
    campaign_refine_parser.add_argument("--create-beads", action="store_true")
    campaign_refine_parser.add_argument("--llm", action="store_true")
    campaign_refine_parser.add_argument("--llm-response")
    campaign_refine_parser.add_argument("--json", action="store_true")
    campaign_refine_parser.set_defaults(handler=_run_campaign_refine)

    campaign_run_parser = campaign_subparsers.add_parser(
        "run",
        help="Prepare one supervised Codex handoff from the current campaign loop.",
    )
    campaign_run_parser.add_argument("campaign")
    campaign_run_parser.add_argument("--driver", default="codex")
    campaign_run_parser.add_argument("--agent", default="codex")
    campaign_run_parser.add_argument("--lease", default="2h")
    campaign_run_parser.add_argument("--supervised", action="store_true")
    campaign_run_parser.add_argument("--managed", action="store_true")
    campaign_run_parser.add_argument("--max-steps", type=int, default=1)
    campaign_run_parser.add_argument("--json", action="store_true")
    campaign_run_parser.set_defaults(handler=_run_campaign_run)

    campaign_sync_beads_parser = campaign_subparsers.add_parser(
        "sync-beads",
        help="Synchronize campaign loop and goal lifecycle state to Beads explicitly.",
    )
    campaign_sync_beads_parser.add_argument("campaign")
    campaign_sync_beads_parser.add_argument("--write", action="store_true")
    campaign_sync_beads_parser.add_argument("--json", action="store_true")
    campaign_sync_beads_parser.set_defaults(handler=_run_campaign_sync_beads)

    return parser


def _add_adoption_subcommands(
    subparsers: Any,
    *,
    handler_prefix: str = "adopt",
) -> None:
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Classify current dp adoption state without mutation.",
    )
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.set_defaults(
        handler=_run_migrate_inspect if handler_prefix == "migrate" else _run_adopt_inspect
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="Plan additive dp adoption or migration.",
    )
    plan_parser.add_argument("--write", action="store_true")
    plan_parser.add_argument("--json", action="store_true")
    plan_parser.set_defaults(
        handler=_run_migrate_plan if handler_prefix == "migrate" else _run_adopt_plan
    )

    apply_parser = subparsers.add_parser(
        "apply",
        help="Dry-run or explicitly apply an adoption plan.",
    )
    apply_parser.add_argument("plan")
    apply_parser.add_argument("--apply", action="store_true")
    apply_parser.add_argument("--json", action="store_true")
    apply_parser.set_defaults(
        handler=_run_migrate_apply if handler_prefix == "migrate" else _run_adopt_apply
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify current adoption health.",
    )
    verify_parser.add_argument("--json", action="store_true")
    verify_parser.set_defaults(
        handler=_run_migrate_verify if handler_prefix == "migrate" else _run_adopt_verify
    )


def _run_trace_coverage(args: argparse.Namespace) -> int:
    spec_paths = _expand_globs(args.spec_globs or list(DEFAULT_SPEC_GLOBS))
    trace_paths = _expand_globs(args.trace_globs or list(DEFAULT_TRACE_GLOBS))

    report = compute_trace_coverage(
        parsed_specs=parse_spec_ids(spec_paths),
        parsed_markers=parse_trace_markers(trace_paths),
    )

    if args.json:
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0

    print(f"total_specs: {report.total_specs}")
    print(f"covered_count: {report.covered_count}")
    print("uncovered_specs:")
    for spec_id in report.uncovered_specs:
        print(f"- {spec_id}")

    return 0


def _run_trace_validate(args: argparse.Namespace) -> int:
    spec_paths = _expand_globs(args.spec_globs or list(DEFAULT_SPEC_GLOBS))
    trace_paths = _expand_globs(args.trace_globs or list(DEFAULT_TRACE_GLOBS))
    parsed_markers, malformed_markers = parse_trace_references(trace_paths)
    report = validate_trace_references(
        parsed_specs=parse_spec_ids(spec_paths),
        parsed_markers=parsed_markers,
        malformed_markers=malformed_markers,
    )

    if args.json:
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0 if report.is_valid else 1

    if report.is_valid:
        print("trace validation passed: no issues found.")
        return 0

    print(f"trace validation failed: {len(report.issues)} issue(s) found.")
    for issue in report.issues:
        print(
            f"- {issue.location.path}:{issue.location.line}:{issue.location.column} "
            f"[{issue.kind}] {issue.message}"
        )
    return 1


def _run_decompose(args: argparse.Namespace) -> int:
    items = list(args.items or [])
    if not items:
        spec_paths = _expand_globs(args.spec_globs or ["docs/specs/**/*.md"])
        items = [f"Implement {entry.spec_id}" for entry in parse_spec_ids(spec_paths)]

    if not items:
        message = "No decomposition items provided. Use --item or provide specs via --spec-glob."
        if args.json:
            print(json.dumps({"ok": False, "error": message}))
        else:
            print(f"dp decompose error: {message}", file=sys.stderr)
        return 2

    try:
        context_window = resolve_context_window(args.context_window, args.preset)
        plan = decompose_items(items, context_window=context_window)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"dp decompose error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = plan.to_dict()
        payload["ok"] = plan.is_dag
        print(json.dumps(payload, sort_keys=True))
        return 0 if plan.is_dag else 1

    print(f"Context window: {plan.context_window}")
    print(f"DAG valid: {str(plan.is_dag).lower()}")
    if not plan.nodes:
        print("No plan nodes generated.")
        return 0
    print("Nodes:")
    for node in plan.nodes:
        dependencies = ", ".join(node.depends_on) if node.depends_on else "none"
        print(
            f"- {node.node_id}: tokens={node.estimated_tokens} "
            f"deps={dependencies} title={node.title}"
        )
    return 0 if plan.is_dag else 1


def _run_progress(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    snapshot = collect_progress_snapshot(Path.cwd())
    previous_snapshot = None

    if args.watch:
        previous_path = (
            Path(args.previous) if args.previous else _latest_progress_snapshot(output_dir)
        )
        if previous_path is not None and previous_path.exists():
            try:
                previous_snapshot = load_snapshot(previous_path)
            except ValueError:
                previous_snapshot = None

    triggers = evaluate_watch_triggers(snapshot, previous_snapshot) if args.watch else ()
    report = ProgressReport(snapshot=snapshot, triggers=triggers)
    json_path, markdown_path = write_progress_report(report, output_dir)

    triggered = any(trigger.triggered for trigger in report.triggers)

    if args.json:
        payload: dict[str, Any] = report.to_dict()
        payload["json_path"] = json_path.as_posix()
        payload["markdown_path"] = markdown_path.as_posix()
        payload["ok"] = not triggered
        print(json.dumps(payload, sort_keys=True))
        return 1 if triggered else 0

    print(f"Progress JSON: {json_path.as_posix()}")
    print(f"Progress Markdown: {markdown_path.as_posix()}")
    print(f"Dirty files: {snapshot.dirty_files}")
    print(f"Spec count: {snapshot.spec_count}")
    print(f"ADR count: {snapshot.adr_count}")
    print(f"Ready issue count: {snapshot.ready_issue_count}")

    if args.watch:
        print("Watch triggers:")
        for trigger in report.triggers:
            state = "TRIGGERED" if trigger.triggered else "not-triggered"
            print(f"- {trigger.name}: {state} ({trigger.reason})")

    return 1 if triggered else 0


def _run_doctor(args: argparse.Namespace) -> int:
    health = check_beads_health()
    payload = {
        "ok": health.ok,
        "checks": {
            "beads": health.to_dict(),
        },
    }

    if args.detail is not None:
        response = wrap_progressive_payload(
            command="doctor",
            command_line=f"dp doctor --json --detail {args.detail}",
            payload=payload,
            exit_code=0 if health.ok else 2,
            detail=args.detail,
        )
        if args.json:
            print(json.dumps(response, sort_keys=True))
        else:
            print(response["summary"])
        return 0 if health.ok else 2

    if args.json:
        print(json.dumps(payload, sort_keys=True))
        return 0 if health.ok else 2

    print(f"Doctor: {'PASS' if health.ok else 'FAIL'}")
    print(f"Beads: {'ok' if health.ok else 'not ready'}")
    if health.bd_version is not None:
        print(f"bd version: {health.bd_version}")
    if health.issue_prefix is not None:
        print(f"issue prefix: {health.issue_prefix}")
    if health.issue_count is not None:
        print(f"issue count: {health.issue_count}")
    for warning in health.warnings:
        print(f"warning: {warning}")
    for error in health.errors:
        print(f"error: {error}", file=sys.stderr)
    if health.recovery_hint is not None:
        print(f"recovery: {health.recovery_hint}", file=sys.stderr)
    return 0 if health.ok else 2


def _run_explain(args: argparse.Namespace) -> int:
    payload, exit_code = explain_code(args.code)
    if args.json or args.format == "json":
        print(json.dumps(payload, sort_keys=True))
        return exit_code

    print(f"# {payload['code']}")
    print()
    print(payload["summary"])
    print()
    print(payload["why_it_matters"])
    print()
    print("Next actions:")
    for action in payload["next_actions"]:
        print(f"- `{action['command']}`: {action['why']}")
    return exit_code


def _run_codex_preflight(args: argparse.Namespace) -> int:
    result = run_codex_preflight(event=args.event, strict=args.strict)
    if args.json:
        print(json.dumps(result.payload, sort_keys=True))
        return result.exit_code

    if result.exit_code == 2:
        error = result.payload.get("error", {})
        message = error.get("message", "unsupported preflight event")
        print(f"dp codex preflight error: {message}", file=sys.stderr)
        return result.exit_code

    print(f"Codex preflight: {'PASS' if result.payload['ok'] else 'BLOCKED'}")
    print(f"Event: {result.payload['event']}")
    print(f"Mode: {result.payload['mode']}")
    print(f"Blocking findings: {result.payload['blocking_count']}")
    print(f"Advisory findings: {result.payload['advisory_count']}")
    for check in result.payload["checks"]:
        print(
            f"- {check['id']} [{check['severity']}/{check['status']}]: "
            f"{check['message']}"
        )
    return result.exit_code


def _run_goal_lint(args: argparse.Namespace) -> int:
    result = lint_goal_file(Path(args.goal))

    if args.json:
        print(json.dumps(result.report.to_dict(), sort_keys=True))
        return result.exit_code

    if result.report.valid:
        print(f"Goal valid: {result.report.goal_id}")
        return 0

    print(f"Goal invalid: {result.report.goal_id or '<unknown>'}")
    for error in result.report.errors:
        print(f"- [{error.code}] {error.path}: {error.message}")
    for warning in result.report.warnings:
        print(f"- [warning:{warning.code}] {warning.path}: {warning.message}")
    return result.exit_code


def _run_goal_status(args: argparse.Namespace) -> int:
    result = goal_status(Path(args.goal))
    if args.detail is not None:
        return _emit_progressive_result(
            command="goal.status",
            command_line=f"dp goal status {args.goal} --json --detail {args.detail}",
            payload=result.payload,
            exit_code=result.exit_code,
            detail=args.detail,
            json_output=args.json,
        )
    return _emit_goal_command_result(result, args.json)


def _run_goal_claim(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(
        claim_goal(Path(args.goal), agent=args.agent, lease=args.lease),
        args.json,
    )


def _run_goal_start(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(
        start_goal(Path(args.goal), agent=args.agent),
        args.json,
    )


def _run_goal_heartbeat(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(heartbeat_goal(Path(args.goal)), args.json)


def _run_goal_block(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(
        block_goal(Path(args.goal), reason=args.reason, write_artifact=args.write_artifact),
        args.json,
    )


def _run_goal_release(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(
        release_goal(Path(args.goal), reason=args.reason),
        args.json,
    )


def _run_goal_complete(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(
        complete_goal(Path(args.goal), evidence_path=Path(args.evidence)),
        args.json,
    )


def _run_goal_verify(args: argparse.Namespace) -> int:
    result = verify_goal(Path(args.goal), evidence_path=Path(args.evidence))
    if args.detail is not None:
        return _emit_progressive_result(
            command="goal.verify",
            command_line=(
                f"dp goal verify {args.goal} --evidence {args.evidence} "
                f"--json --detail {args.detail}"
            ),
            payload=result.payload,
            exit_code=result.exit_code,
            detail=args.detail,
            json_output=args.json,
        )
    return _emit_goal_command_result(
        result,
        args.json,
    )


def _run_goal_emit(args: argparse.Namespace) -> int:
    result = emit_goal_prompt(Path(args.goal), output_format=args.format)
    return _emit_goal_command_result(result, args.json)


def _run_agent_bootstrap(args: argparse.Namespace) -> int:
    result = agent_bootstrap(detail=args.detail)
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_agent_capabilities(args: argparse.Namespace) -> int:
    result = agent_capabilities()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_agent_eval(args: argparse.Namespace) -> int:
    result = agent_eval()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_agent_prompt(args: argparse.Namespace) -> int:
    result = emit_goal_prompt(Path(args.goal), output_format=args.format)
    if result.payload.get("ok") is True:
        result.payload["command"] = "agent.prompt"
    return _emit_goal_command_result(result, args.json)


def _run_agent_launch(args: argparse.Namespace) -> int:
    return _emit_goal_command_result(
        launch_agent_goal(
            Path(args.goal),
            driver=args.driver,
            supervised=args.supervised,
            agent=args.agent,
            lease=args.lease,
        ),
        args.json,
    )


def _run_instructions_inspect(args: argparse.Namespace) -> int:
    result = inspect_instructions(detail=args.detail)
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_instructions_audit(args: argparse.Namespace) -> int:
    result = audit_instructions()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_instructions_plan_update(args: argparse.Namespace) -> int:
    result = plan_instruction_update()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_adopt_inspect(args: argparse.Namespace) -> int:
    result = inspect_adoption()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_adopt_plan(args: argparse.Namespace) -> int:
    result = plan_adoption(write=args.write)
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_adopt_apply(args: argparse.Namespace) -> int:
    result = apply_adoption(Path(args.plan), apply=args.apply)
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_adopt_verify(args: argparse.Namespace) -> int:
    result = verify_adoption()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_migrate_inspect(args: argparse.Namespace) -> int:
    return _run_adopt_inspect(args)


def _run_migrate_plan(args: argparse.Namespace) -> int:
    return _run_adopt_plan(args)


def _run_migrate_apply(args: argparse.Namespace) -> int:
    return _run_adopt_apply(args)


def _run_migrate_verify(args: argparse.Namespace) -> int:
    return _run_adopt_verify(args)


def _run_skills_scaffold(args: argparse.Namespace) -> int:
    result = scaffold_skills(target=args.target)
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_skills_lint(args: argparse.Namespace) -> int:
    result = lint_skills()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_skills_audit(args: argparse.Namespace) -> int:
    result = audit_skills()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_skills_eval(args: argparse.Namespace) -> int:
    result = eval_skills()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_hooks_audit(args: argparse.Namespace) -> int:
    result = audit_hooks()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_hooks_doctor(args: argparse.Namespace) -> int:
    result = doctor_hooks()
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_hooks_scaffold(args: argparse.Namespace) -> int:
    result = scaffold_hooks(target=args.target, write=args.write)
    return _emit_agent_command_result(result.payload, result.exit_code, args.json)


def _run_evidence_lint(args: argparse.Namespace) -> int:
    result = lint_evidence_file(Path(args.evidence))

    if args.json:
        print(json.dumps(result.report.to_dict(), sort_keys=True))
        return result.exit_code

    if result.report.valid:
        print(f"Evidence plan valid: {result.report.evidence_id}")
        return 0

    print(f"Evidence plan invalid: {result.report.evidence_id or '<unknown>'}")
    for error in result.report.errors:
        print(f"- [{error.code}] {error.path}: {error.message}")
    for warning in result.report.warnings:
        print(f"- [warning:{warning.code}] {warning.path}: {warning.message}")
    return result.exit_code


def _run_evidence_run(args: argparse.Namespace) -> int:
    result = run_evidence_file(
        Path(args.evidence),
        output_path=Path(args.output) if args.output else None,
        force=args.force,
    )

    if args.detail is not None:
        command_line = f"dp evidence run {args.evidence} --json --detail {args.detail}"
        if args.output:
            command_line = (
                f"dp evidence run {args.evidence} --output {args.output} "
                f"--json --detail {args.detail}"
            )
        return _emit_progressive_result(
            command="evidence.run",
            command_line=command_line,
            payload=result.payload,
            exit_code=result.exit_code,
            detail=args.detail,
            json_output=args.json,
        )

    if args.json:
        print(json.dumps(result.payload, sort_keys=True))
        return result.exit_code

    if result.payload["ok"] is True:
        print(f"Evidence checks passed: {result.payload['evidence_id']}")
    else:
        error = result.payload.get("error") or {}
        print(f"Evidence checks failed: {result.payload['evidence_id'] or '<unknown>'}")
        if error:
            print(f"- [{error['code']}] {error['path']}: {error['message']}")
    return result.exit_code


def _run_loop_lint(args: argparse.Namespace) -> int:
    result = lint_loop_file(Path(args.loop))

    if args.json:
        print(json.dumps(result.report.to_dict(), sort_keys=True))
        return result.exit_code

    if result.report.valid:
        print(f"Loop ledger valid: {result.report.loop_id}")
        return 0

    print(f"Loop ledger invalid: {result.report.loop_id or '<unknown>'}")
    for error in result.report.errors:
        print(f"- [{error.code}] {error.path}: {error.message}")
    for warning in result.report.warnings:
        print(f"- [warning:{warning.code}] {warning.path}: {warning.message}")
    return result.exit_code


def _run_loop_status(args: argparse.Namespace) -> int:
    return _emit_loop_command_result(loop_status(Path(args.loop)), args.json)


def _run_loop_next(args: argparse.Namespace) -> int:
    result = loop_next(
        Path(args.loop),
        claim=args.claim,
        emit_format=args.emit,
        agent=args.agent,
        lease=args.lease,
    )
    if args.detail is not None:
        flags = []
        if args.claim:
            flags.append("--claim")
        if args.emit:
            flags.extend(["--emit", args.emit])
        flag_text = " ".join(flags)
        command_line = (
            f"dp loop next {args.loop} {flag_text} --json --detail {args.detail}"
        ).replace("  ", " ")
        return _emit_progressive_result(
            command="loop.next",
            command_line=command_line,
            payload=result.payload,
            exit_code=result.exit_code,
            detail=args.detail,
            json_output=args.json,
        )
    return _emit_loop_command_result(result, args.json)


def _run_campaign_init(args: argparse.Namespace) -> int:
    return _emit_campaign_command_result(
        init_campaign_from_primary_spec(args.primary_spec, write=args.write),
        args.json,
    )


def _run_campaign_lint(args: argparse.Namespace) -> int:
    result = lint_campaign_file(Path(args.campaign))

    if args.json:
        print(json.dumps(result.report.to_dict(), sort_keys=True))
        return result.exit_code

    if result.report.valid:
        print(f"Campaign valid: {result.report.campaign_id}")
        return 0

    print(f"Campaign invalid: {result.report.campaign_id or '<unknown>'}")
    for error in result.report.errors:
        print(f"- [{error.code}] {error.path}: {error.message}")
    for warning in result.report.warnings:
        print(f"- [warning:{warning.code}] {warning.path}: {warning.message}")
    return result.exit_code


def _run_campaign_status(args: argparse.Namespace) -> int:
    result = campaign_status(Path(args.campaign))
    if args.detail is not None:
        return _emit_progressive_result(
            command="campaign.status",
            command_line=f"dp campaign status {args.campaign} --json --detail {args.detail}",
            payload=result.payload,
            exit_code=result.exit_code,
            detail=args.detail,
            json_output=args.json,
        )
    return _emit_campaign_command_result(result, args.json)


def _run_campaign_recover(args: argparse.Namespace) -> int:
    return _emit_campaign_command_result(campaign_recover(Path(args.campaign)), args.json)


def _run_campaign_ready(args: argparse.Namespace) -> int:
    return _emit_campaign_command_result(
        ready_campaign(Path(args.campaign), write=args.write),
        args.json,
    )


def _run_campaign_refine(args: argparse.Namespace) -> int:
    return _emit_campaign_command_result(
        refine_campaign(
            Path(args.campaign),
            write=args.write,
            create_beads=args.create_beads,
            llm=args.llm,
            llm_response=Path(args.llm_response) if args.llm_response is not None else None,
        ),
        args.json,
    )


def _run_campaign_run(args: argparse.Namespace) -> int:
    return _emit_campaign_command_result(
        run_campaign_once(
            Path(args.campaign),
            driver=args.driver,
            supervised=args.supervised,
            agent=args.agent,
            lease=args.lease,
            managed=args.managed,
            max_steps=args.max_steps,
        ),
        args.json,
    )


def _run_campaign_sync_beads(args: argparse.Namespace) -> int:
    return _emit_campaign_command_result(
        sync_campaign_beads(
            Path(args.campaign),
            write=args.write,
        ),
        args.json,
    )


def _emit_agent_command_result(payload: dict[str, Any], exit_code: int, json_output: bool) -> int:
    if json_output:
        print(json.dumps(payload, sort_keys=True))
        return exit_code
    summary = payload.get("summary") or payload.get("status") or payload.get("command") or "ok"
    print(str(summary))
    return exit_code


def _emit_progressive_result(
    *,
    command: str,
    command_line: str,
    payload: dict[str, Any],
    exit_code: int,
    detail: str,
    json_output: bool,
) -> int:
    response = wrap_progressive_payload(
        command=command,
        command_line=command_line,
        payload=payload,
        exit_code=exit_code,
        detail=detail,
    )
    if json_output:
        print(json.dumps(response, sort_keys=True))
    else:
        print(response["summary"])
    return exit_code


def _emit_campaign_command_result(result: Any, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.payload, sort_keys=True))
        return int(result.exit_code)

    if result.payload.get("ok") is True:
        command = result.payload.get("command")
        campaign_id = result.payload.get("campaign_id")
        if command == "campaign.init":
            print(f"Campaign scaffold: {campaign_id}")
        elif command == "campaign.recover":
            print(f"Campaign recoverable: {campaign_id}")
        else:
            print(f"Campaign ok: {campaign_id}")
        return int(result.exit_code)

    print(f"Campaign command failed: {result.payload.get('command', '<unknown>')}")
    error = result.payload.get("error")
    if isinstance(error, dict):
        print(f"- [{error.get('code')}] {error.get('message')}")
    lint = result.payload.get("lint")
    if isinstance(lint, dict):
        for item in lint.get("errors", []):
            if isinstance(item, dict):
                print(f"- [{item.get('code')}] {item.get('path')}: {item.get('message')}")
    return int(result.exit_code)


def _emit_loop_command_result(result: Any, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.payload, sort_keys=True))
        return int(result.exit_code)

    if result.payload.get("ok") is True:
        command = result.payload.get("command")
        loop_id = result.payload.get("loop_id")
        if command == "loop.next":
            print(f"Next goal: {result.payload.get('goal_id')} from {loop_id}")
        else:
            print(f"Loop ok: {loop_id}")
        return int(result.exit_code)

    print(f"Loop command failed: {result.payload.get('command', '<unknown>')}")
    error = result.payload.get("error")
    if isinstance(error, dict):
        print(f"- [{error.get('code')}] {error.get('message')}")
    lint = result.payload.get("lint")
    if isinstance(lint, dict):
        for item in lint.get("errors", []):
            if isinstance(item, dict):
                print(f"- [{item.get('code')}] {item.get('path')}: {item.get('message')}")
    return int(result.exit_code)


def _emit_goal_command_result(result: Any, json_output: bool) -> int:
    if json_output:
        print(json.dumps(result.payload, sort_keys=True))
        return int(result.exit_code)

    if result.payload.get("ok") is True:
        if "codex_goal" in result.payload:
            print(result.payload["codex_goal"])
        else:
            state = result.payload.get("state", "ok")
            goal_id = result.payload.get("goal_id", "<unknown>")
            print(f"Goal {goal_id}: {state}")
        return int(result.exit_code)

    error = result.payload.get("error")
    if isinstance(error, dict):
        message = error.get("message", "goal command failed.")
    else:
        message = "goal command failed."
    print(f"dp goal error: {message}", file=sys.stderr)
    return int(result.exit_code)


def _run_adr_create(args: argparse.Namespace) -> int:
    try:
        record = create_adr(args.title, directory=DEFAULT_ADR_DIRECTORY, status=args.status)
    except ValueError as exc:
        return _handle_adr_error(args.json, str(exc))

    if args.json:
        print(json.dumps({"ok": True, "adr": record.to_dict()}, sort_keys=True))
        return 0

    print(f"Created {record.adr_id} ({record.status}): {record.path}")
    return 0


def _run_adr_list(args: argparse.Namespace) -> int:
    records = list_adrs(DEFAULT_ADR_DIRECTORY)
    if args.json:
        print(
            json.dumps(
                {"ok": True, "items": [record.to_dict() for record in records]},
                sort_keys=True,
            )
        )
        return 0

    if not records:
        print("No ADRs found.")
        return 0

    for record in records:
        print(f"{record.adr_id} {record.status} {record.title} ({record.path})")
    return 0


def _run_adr_show(args: argparse.Namespace) -> int:
    try:
        record, content = show_adr(args.identifier, DEFAULT_ADR_DIRECTORY)
    except ValueError as exc:
        return _handle_adr_error(args.json, str(exc))

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "adr": record.to_dict(),
                    "content": content,
                },
                sort_keys=True,
            )
        )
        return 0

    print(content, end="" if content.endswith("\n") else "\n")
    return 0


def _run_adr_update(args: argparse.Namespace) -> int:
    try:
        record = update_adr_status(
            args.identifier,
            status=args.status,
            directory=DEFAULT_ADR_DIRECTORY,
            superseded_by=args.superseded_by,
        )
    except ValueError as exc:
        return _handle_adr_error(args.json, str(exc))

    if args.json:
        print(json.dumps({"ok": True, "adr": record.to_dict()}, sort_keys=True))
        return 0

    print(f"Updated {record.adr_id} -> {record.status}")
    return 0


def _handle_adr_error(json_output: bool, error: str) -> int:
    if json_output:
        print(json.dumps({"ok": False, "error": error}, sort_keys=True))
    else:
        print(f"dp adr error: {error}", file=sys.stderr)
    return 2


def _run_review(args: argparse.Namespace) -> int:
    report = run_review(Path.cwd())

    if args.json:
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0 if report.ready_to_commit else 1

    readiness = "READY" if report.ready_to_commit else "NOT READY"
    print(f"Commit readiness: {readiness}")
    print(f"Blocking findings: {report.blocking_count}")
    print(f"Advisory findings: {report.advisory_count}")

    if not report.findings:
        print("No findings.")
        return 0

    for finding in report.findings:
        location = ""
        if finding.path is not None:
            location = finding.path
            if finding.line is not None:
                location = f"{location}:{finding.line}"
            location = f" ({location})"
        print(f"- [{finding.severity}] {finding.check_id}{location}: {finding.message}")

    return 0 if report.ready_to_commit else 1


def _run_verify(args: argparse.Namespace) -> int:
    if args.goal:
        result = verify_goal_orchestrated(
            Path(args.goal),
            evidence_path=Path(args.evidence) if args.evidence else None,
            evidence_output=Path(args.evidence_output) if args.evidence_output else None,
            force=args.force,
        )
        if args.json:
            print(json.dumps(result.payload, sort_keys=True))
            return result.exit_code
        if result.payload["ok"] is True:
            print(f"Goal verified: {result.payload['goal_id']}")
            return 0
        error = result.payload.get("error") or {}
        print(f"Goal verification failed: {result.payload.get('goal_id') or '<unknown>'}")
        if error:
            print(f"- [{error['code']}] {error['path']}: {error['message']}")
        return result.exit_code

    manifest_path = Path(args.manifest)

    try:
        report = run_goal_backward_verify(manifest_path)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc), "outcome": "failed", "levels": []}))
        else:
            print(f"dp verify error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload: dict[str, Any] = report.to_dict()
        payload["ok"] = report.outcome == "verified"
        print(json.dumps(payload, sort_keys=True))
        return _verify_exit_code(report.outcome)

    print(f"Overall outcome: {report.outcome}")
    for level in report.levels:
        print(f"- {level.level}: {level.status} ({level.passed}/{level.total})")
        for detail in level.details:
            print(f"  * {detail}")
    return _verify_exit_code(report.outcome)


def _verify_exit_code(outcome: str) -> int:
    if outcome == "verified":
        return 0
    if outcome == "incomplete":
        return 2
    return 1


def _run_policy_validate(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    try:
        policy = load_policy_config(config_path)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"dp policy error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"ok": True, "policy": policy.to_dict()}, sort_keys=True))
        return 0

    print(f"Policy mode: {policy.mode}")
    print("Checks:")
    for check_name, enabled in sorted(policy.checks.items()):
        state = "enabled" if enabled else "disabled"
        print(f"- {check_name}: {state}")
    return 0


def _run_enforce(args: argparse.Namespace) -> int:
    try:
        report = run_enforcement(
            stage=args.stage,
            policy_path=Path(args.policy),
            repo_root=Path.cwd(),
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"dp enforce error: {exc}", file=sys.stderr)
        return 2

    exit_code = 1 if report.blocked else 0

    if args.json:
        payload = report.to_dict()
        payload["ok"] = not report.blocked
        print(json.dumps(payload, sort_keys=True))
        return exit_code

    print(f"Enforcement stage: {report.stage}")
    print(f"Policy mode: {report.mode} ({report.policy_path})")

    if report.bypassed:
        print("Bypass: active")
        print(f"Reason: {report.bypass_reason}")
        return 0

    for check in report.checks:
        print(f"- {check.check}: {check.status} (blocking={str(check.blocking).lower()})")
        if check.command is not None:
            print(f"  command: {check.command}")
        print(f"  message: {check.message}")

    if report.blocked:
        print("Result: BLOCKED")
        print(
            "Emergency bypass: set DP_BYPASS_ENFORCEMENT=1 "
            "and DP_BYPASS_REASON='<reason>' for one run."
        )
    else:
        print("Result: PASS")

    return exit_code


def _latest_progress_snapshot(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    candidates = sorted(output_dir.glob("progress-*.json"))
    if not candidates:
        return None
    return candidates[-1]


def _run_task_ready(args: argparse.Namespace) -> int:
    return _execute_bd(["ready"], json_output=args.json, command_name="task.ready")


# @trace SPEC-70.02
def _run_task_claim(args: argparse.Namespace) -> int:
    command = (
        ["ready", "--claim"]
        if args.issue_id is None
        else ["update", args.issue_id, "--claim"]
    )
    if not args.json:
        return _execute_bd(command, json_output=False, command_name="task.claim")

    effective_command = [*command, "--json"]
    try:
        result = run_bd(effective_command)
    except BdUnavailableError as exc:
        _emit_task_json(
            "task.claim",
            exit_code=127,
            ok=False,
            error=str(exc),
            beads_command=effective_command,
        )
        return 127
    except BeadsNotInitializedError as exc:
        _emit_task_json(
            "task.claim",
            exit_code=2,
            ok=False,
            error=str(exc),
            beads_command=effective_command,
        )
        return 2

    data: Any = None
    raw_output = result.stdout.strip()
    if raw_output:
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            data = None
    context = _task_intake_context(data) if result.returncode == 0 else None
    _emit_task_json(
        "task.claim",
        exit_code=result.returncode,
        ok=result.returncode == 0,
        data=data,
        stderr=result.stderr.strip() or None,
        raw_output=raw_output if data is None and raw_output else None,
        context=context,
        beads_command=effective_command,
    )
    return result.returncode


def _run_task_show(args: argparse.Namespace) -> int:
    return _execute_bd(
        ["show", args.issue_id],
        json_output=args.json,
        command_name="task.show",
    )


def _run_task_update(args: argparse.Namespace) -> int:
    command = ["update", args.issue_id]
    if args.status is not None:
        try:
            status = normalize_status(args.status)
        except ValueError as exc:
            print(f"dp task error: {exc}", file=sys.stderr)
            return 2
        command.extend(["--status", status])
    if args.priority is not None:
        try:
            priority = normalize_priority(args.priority)
        except ValueError as exc:
            print(f"dp task error: {exc}", file=sys.stderr)
            return 2
        command.extend(["--priority", priority])
    if args.owner is not None:
        command.extend(["--owner", args.owner])
    return _execute_bd(
        command,
        json_output=args.json,
        command_name="task.update",
    )


def _run_task_close(args: argparse.Namespace) -> int:
    return _execute_bd(
        ["close", args.issue_id, "--reason", args.reason],
        json_output=args.json,
        command_name="task.close",
    )


def _run_task_discover(args: argparse.Namespace) -> int:
    if args.priority is not None:
        try:
            priority = normalize_priority(args.priority)
        except ValueError as exc:
            print(f"dp task error: {exc}", file=sys.stderr)
            return 2
    else:
        priority = None

    command = [
        "create",
        args.title,
        "--type",
        "task",
        "--deps",
        f"discovered-from:{args.source_id},blocks:{args.source_id}",
    ]
    if args.description is not None:
        command.extend(["--description", args.description])
    if args.acceptance is not None:
        command.extend(["--acceptance", args.acceptance])
    if priority is not None:
        command.extend(["--priority", priority])
    if args.labels is not None:
        command.extend(["--labels", args.labels])
    if args.assignee is not None:
        command.extend(["--assignee", args.assignee])
    if args.dry_run:
        command.append("--dry-run")
    return _execute_bd(
        command,
        json_output=args.json,
        command_name="task.discover",
    )


def _execute_bd(command: list[str], *, json_output: bool, command_name: str) -> int:
    effective_command = [*command, "--json"] if json_output else command

    try:
        result = run_bd(effective_command)
    except BdUnavailableError as exc:
        if json_output:
            _emit_task_json(command_name, exit_code=127, ok=False, error=str(exc))
            return 127
        print(f"dp task error: {exc}", file=sys.stderr)
        return 127
    except BeadsNotInitializedError as exc:
        if json_output:
            _emit_task_json(command_name, exit_code=2, ok=False, error=str(exc))
            return 2
        print(f"dp task error: {exc}", file=sys.stderr)
        return 2

    if json_output:
        data: Any = None
        raw_output = result.stdout.strip()
        if raw_output:
            try:
                data = json.loads(raw_output)
            except json.JSONDecodeError:
                data = None
        _emit_task_json(
            command_name,
            exit_code=result.returncode,
            ok=result.returncode == 0,
            data=data,
            stderr=result.stderr.strip() or None,
            raw_output=raw_output if data is None and raw_output else None,
        )
        return result.returncode

    _emit_stream(sys.stdout, result.stdout)

    if result.returncode != 0:
        error_message = result.stderr.strip() or "bd command failed."
        print(f"dp task error: {error_message}", file=sys.stderr)
        return result.returncode

    _emit_stream(sys.stderr, result.stderr)
    return 0


def _emit_stream(stream: TextIO, content: str) -> None:
    if not content:
        return
    print(content, file=stream, end="" if content.endswith("\n") else "\n")


def _emit_task_json(
    command: str,
    *,
    exit_code: int,
    ok: bool,
    data: Any = None,
    stderr: str | None = None,
    error: str | None = None,
    raw_output: str | None = None,
    context: dict[str, Any] | None = None,
    beads_command: list[str] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "command": command,
        "ok": ok,
        "exit_code": exit_code,
        "data": data,
        "stderr": stderr,
        "error": error,
    }
    if raw_output is not None:
        payload["raw_output"] = raw_output
    if context is not None:
        payload["context"] = context
    if beads_command is not None:
        payload["beads_command"] = beads_command
    print(json.dumps(payload, sort_keys=True))


def _task_intake_context(data: Any) -> dict[str, Any]:
    issue = _claimed_issue(data)
    warnings: list[str] = []
    if issue is None:
        return {
            "issue_id": None,
            "title": None,
            "spec_id": None,
            "labels": [],
            "parent": None,
            "dependencies": [],
            "dependents": [],
            "read_first": [],
            "mentioned_paths": [],
            "warnings": ["No claimed issue object found in Beads JSON output."],
        }

    issue_id = _string_or_none(issue.get("id"))
    title = _string_or_none(issue.get("title"))
    spec_id = _string_or_none(issue.get("spec_id"))
    labels = _string_list(issue.get("labels"))
    parent = _string_or_none(issue.get("parent"))
    dependencies = _issue_ids(issue.get("dependencies"))
    dependents = _issue_ids(issue.get("dependents"))
    text_fields = [
        title,
        spec_id,
        _string_or_none(issue.get("description")),
        _string_or_none(issue.get("design")),
        _string_or_none(issue.get("acceptance_criteria")),
        _string_or_none(issue.get("notes")),
    ]
    mentioned_paths = _mentioned_paths("\n".join(value for value in text_fields if value))
    read_first = _read_first_paths(spec_id, mentioned_paths)
    if not mentioned_paths and spec_id is None:
        warnings.append(
            "Claimed issue does not mention files or a spec id; inspect the issue before editing."
        )
    if not _string_or_none(issue.get("acceptance_criteria")):
        warnings.append("Claimed issue has no acceptance criteria.")

    return {
        "issue_id": issue_id,
        "title": title,
        "spec_id": spec_id,
        "labels": labels,
        "parent": parent,
        "dependencies": dependencies,
        "dependents": dependents,
        "read_first": read_first,
        "mentioned_paths": mentioned_paths,
        "warnings": warnings,
    }


def _claimed_issue(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        for key in ("issue", "claimed", "data"):
            nested = data.get(key)
            if isinstance(nested, dict):
                return nested
        items = data.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    return item
        if isinstance(data.get("id"), str):
            return data
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                return item
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _issue_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            ids.append(item)
        elif isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.append(item["id"])
        elif isinstance(item, dict) and isinstance(item.get("issue_id"), str):
            ids.append(item["issue_id"])
    return sorted(set(ids))


def _mentioned_paths(text: str) -> list[str]:
    candidates = set(
        _strip_path_punctuation(match)
        for match in re.findall(
            (
                r"(?<![\w./-])(?:[A-Za-z0-9_.-]+/)+"
                r"[A-Za-z0-9_.@+-]+(?:\.[A-Za-z0-9]+)?"
            ),
            text,
        )
    )
    root_files = {"AGENTS.md", "README.md", "Makefile", "pyproject.toml", "dp-policy.json"}
    for file_name in root_files:
        if file_name in text:
            candidates.add(file_name)
    return sorted(
        path for path in candidates if _is_context_path(path) and _is_likely_repo_path(path)
    )


def _strip_path_punctuation(value: str) -> str:
    return value.rstrip(".,;:)]}'\"")


def _read_first_paths(spec_id: str | None, mentioned_paths: list[str]) -> list[str]:
    read_first: list[str] = []
    if spec_id is not None:
        spec_path = _spec_path_for_id(spec_id)
        if spec_path is not None:
            read_first.append(spec_path)
    for path in mentioned_paths:
        if _is_read_first_path(path) and path not in read_first:
            read_first.append(path)
    return read_first


def _spec_path_for_id(spec_id: str) -> str | None:
    specs_dir = Path("docs/specs")
    if not specs_dir.exists():
        return None
    needle = f"[{spec_id}]"
    for path in sorted(specs_dir.glob("*.md")):
        try:
            if needle in path.read_text(encoding="utf-8"):
                return path.as_posix()
        except OSError:
            continue
    return None


def _is_context_path(value: str) -> bool:
    if (
        "\x00" in value
        or "\\" in value
        or value.startswith(("http://", "https://", "-", "~"))
    ):
        return False
    path = Path(value)
    if path.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in path.parts)


def _is_likely_repo_path(value: str) -> bool:
    path = Path(value)
    if path.exists():
        return True
    return bool(path.suffix)


def _is_read_first_path(value: str) -> bool:
    path = Path(value)
    if path.is_file():
        return True
    return bool(path.suffix)


def _expand_globs(patterns: Sequence[str]) -> list[Path]:
    unique_paths: set[Path] = set()

    for pattern in patterns:
        unique_paths.update(path for path in Path.cwd().glob(pattern) if path.is_file())

    return sorted(unique_paths, key=lambda path: path.as_posix())
