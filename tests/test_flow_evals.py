from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from jsonschema import validate

from dp.cli.main import main
from dp.providers.beads import BeadsHealth, CommandResult

REPO_ROOT = Path(__file__).resolve().parents[1]
FLOW_ISSUE_ID = "dpcx-flow.1"
FLOW_SPEC_ID = "SPEC-70.05"


# @trace SPEC-70.05
def test_spec70_flow_eval_reports_friction_metrics(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    state = {"status": "open"}
    task_calls = _install_fake_task_beads(monkeypatch, state)
    _install_fake_preflight(monkeypatch, state)
    _install_fake_doctor(monkeypatch)

    doctor_payload = _run_json(["doctor", "--json"], capsys)
    claim_payload = _run_json(["task", "claim", FLOW_ISSUE_ID, "--json"], capsys)
    written_files = _write_implementation_artifacts()
    preflight_payload = _run_json(
        ["codex", "preflight", "--event", "stop", "--strict", "--json"],
        capsys,
    )
    verify_payload = _run_json(
        ["verify", "--manifest", "docs/verify/manifest.json", "--json"], capsys
    )
    close_payload = _run_json(
        ["task", "close", FLOW_ISSUE_ID, "--reason", "flow eval complete", "--json"],
        capsys,
    )

    summary = _build_summary(
        doctor_payload=doctor_payload,
        claim_payload=claim_payload,
        preflight_payload=preflight_payload,
        verify_payload=verify_payload,
        close_payload=close_payload,
        task_calls=task_calls,
        written_files=written_files,
    )
    summary_paths = _write_summary(summary)

    schema = json.loads(
        (REPO_ROOT / "docs/schemas/flow-eval-summary.schema.json").read_text(encoding="utf-8")
    )
    validate(instance=summary, schema=schema)

    assert summary_paths["json"].exists()
    assert summary_paths["markdown"].exists()
    assert _read_json(summary_paths["json"]) == summary
    assert summary["metrics"]["setup_recovery_ok"] is True
    assert summary["metrics"]["claim_round_trips"] == 1
    assert summary["metrics"]["evidence_completeness"] == 1.0
    assert summary["friction"]["false_positive_preflight_blocks"] == 0
    assert summary["friction"]["manual_interventions_required"] == 0
    assert summary["friction"]["open_blockers"] == 0
    assert "SPEC-70.05 Flow Eval" in summary_paths["markdown"].read_text(encoding="utf-8")


def _install_fake_doctor(monkeypatch) -> None:
    cli_main = importlib.import_module("dp.cli.main")
    monkeypatch.setattr(cli_main, "check_beads_health", _healthy_beads)


def _install_fake_preflight(monkeypatch, state: dict[str, str]) -> None:
    preflight = importlib.import_module("dp.core.codex_preflight")
    monkeypatch.setattr(preflight, "check_beads_health", _healthy_beads)
    monkeypatch.setattr(preflight, "run_bd", lambda _: _preflight_beads(state))
    monkeypatch.setattr(
        preflight,
        "_git_changed_files",
        lambda: (
            [
                "dp/core/flow_eval_feature.py",
                "tests/test_flow_eval_feature.py",
                "docs/evidence/flow-eval-proof.txt",
            ],
            None,
        ),
    )


def _install_fake_task_beads(monkeypatch, state: dict[str, str]) -> list[list[str]]:
    cli_main = importlib.import_module("dp.cli.main")
    calls: list[list[str]] = []

    def fake_run_bd(args: Sequence[str]) -> CommandResult:
        calls.append(list(args))
        if list(args) == ["update", FLOW_ISSUE_ID, "--claim", "--json"]:
            state["status"] = "in_progress"
            return CommandResult(returncode=0, stdout=json.dumps(_issue(state)) + "\n", stderr="")
        if list(args) == [
            "close",
            FLOW_ISSUE_ID,
            "--reason",
            "flow eval complete",
            "--json",
        ]:
            state["status"] = "closed"
            return CommandResult(returncode=0, stdout=json.dumps(_issue(state)) + "\n", stderr="")
        return CommandResult(returncode=2, stdout="", stderr=f"unexpected bd args: {list(args)}")

    monkeypatch.setattr(cli_main, "run_bd", fake_run_bd)
    return calls


def _preflight_beads(state: dict[str, str]) -> CommandResult:
    payload = [_issue(state)] if state["status"] == "in_progress" else []
    return CommandResult(returncode=0, stdout=json.dumps(payload) + "\n", stderr="")


def _issue(state: dict[str, str]) -> dict[str, Any]:
    return {
        "id": FLOW_ISSUE_ID,
        "title": "Flow eval task",
        "spec_id": FLOW_SPEC_ID,
        "status": state["status"],
        "issue_type": "task",
        "labels": ["pilot", "friction", "m7"],
        "description": (
            "Expected files: dp/core/flow_eval_feature.py, "
            "tests/test_flow_eval_feature.py, docs/evidence/flow-eval-proof.txt."
        ),
        "acceptance_criteria": "Doctor, claim, implement, verify, preflight, and close all pass.",
    }


def _healthy_beads() -> BeadsHealth:
    return BeadsHealth(
        ok=True,
        repo_root="/pilot",
        beads_dir="/pilot/.beads",
        bd_available=True,
        bd_version="bd version 1.0.4",
        initialized=True,
        issue_prefix="dpcx",
        issue_count=1,
        ready_count=1,
        sync_command_available=False,
        warnings=(),
        errors=(),
        recovery_hint=None,
    )


def _write_implementation_artifacts() -> list[str]:
    files = {
        "dp/__init__.py": "",
        "dp/core/__init__.py": "",
        "dp/core/flow_eval_feature.py": (
            "# @trace SPEC-70.05\n\n"
            "def normalize_report(value: str) -> str:\n"
            "    return value.strip().lower()\n"
        ),
        "tests/test_flow_eval_feature.py": (
            "from dp.core.flow_eval_feature import normalize_report\n\n\n"
            "def test_normalize_report() -> None:\n"
            "    assert normalize_report(' PASS ') == 'pass'\n"
        ),
        "docs/evidence/flow-eval-proof.txt": "flow eval proof\n",
    }
    for path, content in files.items():
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    command_argv = [sys.executable, "-m", "pytest", "tests/test_flow_eval_feature.py", "-q"]
    command_result = subprocess.run(
        command_argv,
        capture_output=True,
        check=False,
        text=True,
    )

    evidence_path = Path("docs/evidence/flow-eval-proof.txt")
    digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    manifest = {
        "truths": [{"id": "T1", "verified": True}],
        "artifacts": [
            {
                "id": "A1",
                "path": evidence_path.as_posix(),
                "sha256": f"sha256:{digest}",
                "command": {
                    "argv": command_argv,
                    "exit_code": command_result.returncode,
                    "success_exit_codes": [0],
                },
                "task_id": FLOW_ISSUE_ID,
                "spec_id": FLOW_SPEC_ID,
            }
        ],
        "links": [{"truth_id": "T1", "artifact_id": "A1"}],
    }
    manifest_path = Path("docs/verify/manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return [*files.keys(), manifest_path.as_posix()]


def _run_json(args: list[str], capsys) -> dict[str, Any]:
    exit_code = main(args)
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0, payload
    return payload


def _build_summary(
    *,
    doctor_payload: dict[str, Any],
    claim_payload: dict[str, Any],
    preflight_payload: dict[str, Any],
    verify_payload: dict[str, Any],
    close_payload: dict[str, Any],
    task_calls: list[list[str]],
    written_files: list[str],
) -> dict[str, Any]:
    verified_levels = sum(1 for level in verify_payload["levels"] if level["status"] == "verified")
    total_levels = len(verify_payload["levels"])
    claim_round_trips = sum(1 for call in task_calls if "--claim" in call)
    return {
        "schema_version": "0.1",
        "spec_id": FLOW_SPEC_ID,
        "scenario": "guided_task_to_verify_close",
        "steps": [
            _step("doctor", doctor_payload),
            _step("claim", claim_payload),
            {"id": "implement", "ok": True, "exit_code": 0},
            _step("preflight", preflight_payload),
            _step("verify", verify_payload),
            _step("close", close_payload),
        ],
        "metrics": {
            "setup_recovery_ok": (
                doctor_payload["ok"] and doctor_payload["checks"]["beads"]["recovery_hint"] is None
            ),
            "claim_round_trips": claim_round_trips,
            "implementation_artifacts_written": len(written_files),
            "evidence_levels_verified": verified_levels,
            "evidence_levels_total": total_levels,
            "evidence_completeness": verified_levels / total_levels,
            "strict_preflight_blocking_count": preflight_payload["blocking_count"],
            "closeout_exit_code": close_payload["exit_code"],
        },
        "friction": {
            "false_positive_preflight_blocks": preflight_payload["blocking_count"],
            "manual_interventions_required": 0,
            "open_blockers": 0,
        },
        "artifacts": {
            "written_files": written_files,
            "verify_manifest": "docs/verify/manifest.json",
            "evidence_artifact": "docs/evidence/flow-eval-proof.txt",
        },
    }


def _step(step_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if "exit_code" in payload:
        exit_code = int(payload["exit_code"])
    elif "outcome" in payload:
        exit_code = 0 if payload["outcome"] == "verified" else 1
    else:
        exit_code = 0 if payload.get("ok") else 1
    return {
        "id": step_id,
        "ok": bool(payload.get("ok", exit_code == 0)),
        "exit_code": exit_code,
    }


def _write_summary(summary: dict[str, Any]) -> dict[str, Path]:
    output_dir = Path("docs/pilot")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "SPEC-70.05-guided-task-flow-summary.json"
    markdown_path = output_dir / "SPEC-70.05-guided-task-flow-summary.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown_summary(summary), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _render_markdown_summary(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    friction = summary["friction"]
    return (
        "# SPEC-70.05 Flow Eval\n\n"
        f"- Scenario: `{summary['scenario']}`\n"
        f"- Setup recovery ok: {str(metrics['setup_recovery_ok']).lower()}\n"
        f"- Claim round trips: {metrics['claim_round_trips']}\n"
        f"- Evidence completeness: {metrics['evidence_completeness']:.2f}\n"
        f"- Strict preflight blocking findings: {metrics['strict_preflight_blocking_count']}\n"
        f"- False-positive preflight blocks: {friction['false_positive_preflight_blocks']}\n"
        f"- Manual interventions required: {friction['manual_interventions_required']}\n"
        f"- Open blockers: {friction['open_blockers']}\n"
        f"- Closeout exit code: {metrics['closeout_exit_code']}\n"
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
