from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO, cast

from dp.core.adr import create_adr, list_adrs, show_adr, update_adr_status
from dp.core.coverage import compute_trace_coverage
from dp.core.decompose import decompose_items, resolve_context_window
from dp.core.policy import load_policy_config
from dp.core.progress import (
    ProgressReport,
    collect_progress_snapshot,
    evaluate_watch_triggers,
    load_snapshot,
    write_progress_report,
)
from dp.core.review import run_review
from dp.core.spec_parser import parse_spec_ids
from dp.core.task_normalization import normalize_priority, normalize_status
from dp.core.trace_parser import parse_trace_markers, parse_trace_references
from dp.core.validation import validate_trace_references
from dp.core.verify import run_goal_backward_verify
from dp.enforcement import run_enforcement
from dp.providers.beads import BdUnavailableError, BeadsNotInitializedError, run_bd

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

    return parser


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
    print(json.dumps(payload, sort_keys=True))


def _expand_globs(patterns: Sequence[str]) -> list[Path]:
    unique_paths: set[Path] = set()

    for pattern in patterns:
        unique_paths.update(path for path in Path.cwd().glob(pattern) if path.is_file())

    return sorted(unique_paths, key=lambda path: path.as_posix())
