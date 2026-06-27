from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dp.core.evidence_artifacts import (
    default_evidence_run_path,
    validate_evidence_output_path,
)
from dp.core.evidence_lint import lint_evidence_file
from dp.core.evidence_run import run_evidence_file
from dp.core.goal_lint import lint_goal_file
from dp.core.goal_state import verify_goal

# @trace SPEC-80.17


@dataclass(frozen=True)
class GoalVerificationResult:
    payload: dict[str, Any]
    exit_code: int


def verify_goal_orchestrated(
    goal_path: Path,
    *,
    evidence_path: Path | None = None,
    evidence_output: Path | None = None,
    force: bool = False,
) -> GoalVerificationResult:
    if evidence_path is not None and evidence_output is not None:
        return _result(
            ok=False,
            goal_id=None,
            goal_path=goal_path,
            evidence_path=evidence_path,
            evidence_plan_path=None,
            stages={
                "goal_lint": None,
                "evidence_lint": None,
                "evidence_run": None,
                "trace": None,
                "goal_verify": None,
            },
            error=_error(
                "ambiguous_evidence_input",
                "$.evidence",
                "Use --evidence for an existing artifact or --evidence-output for a generated "
                "one, not both.",
            ),
            exit_code=2,
        )

    goal_lint = lint_goal_file(goal_path)
    stages: dict[str, Any] = {
        "goal_lint": _lint_stage(goal_lint.report.to_dict(), goal_lint.exit_code),
        "evidence_lint": None,
        "evidence_run": None,
        "trace": None,
        "goal_verify": None,
    }
    if goal_lint.exit_code != 0:
        return _result(
            ok=False,
            goal_id=goal_lint.report.goal_id,
            goal_path=goal_path,
            evidence_path=evidence_path,
            evidence_plan_path=None,
            stages=stages,
            error=_error(
                "invalid_goal_contract",
                "$",
                "GoalContract failed deterministic lint.",
            ),
            exit_code=goal_lint.exit_code,
        )

    contract = _read_json_object(goal_path)
    goal_id = str(contract["id"])
    goal_evidence_plan = _goal_evidence_plan_path(contract)
    stages["trace"] = _trace_stage(contract)
    if goal_evidence_plan is None:
        return _result(
            ok=False,
            goal_id=goal_id,
            goal_path=goal_path,
            evidence_path=evidence_path,
            evidence_plan_path=None,
            stages=stages,
            error=_error(
                "missing_goal_evidence_plan",
                "$.evidence.evidence_plan",
                "GoalContract must reference an evidence_plan for dp verify --goal.",
            ),
            exit_code=2,
        )

    evidence_plan_path = Path(goal_evidence_plan)
    evidence_lint = lint_evidence_file(evidence_plan_path)
    stages["evidence_lint"] = _lint_stage(evidence_lint.report.to_dict(), evidence_lint.exit_code)
    if evidence_lint.exit_code != 0:
        return _result(
            ok=False,
            goal_id=goal_id,
            goal_path=goal_path,
            evidence_path=evidence_path,
            evidence_plan_path=evidence_plan_path,
            stages=stages,
            error=_error(
                "invalid_evidence_plan",
                "$.evidence.evidence_plan",
                "EvidencePlan failed deterministic lint.",
            ),
            exit_code=evidence_lint.exit_code,
        )

    verify_evidence_path = evidence_path
    source = "supplied"
    if verify_evidence_path is None:
        source = "generated"
        verify_evidence_path = evidence_output or default_evidence_run_path(goal_id)
        output_error = validate_evidence_output_path(verify_evidence_path)
        if output_error is not None:
            return _result(
                ok=False,
                goal_id=goal_id,
                goal_path=goal_path,
                evidence_path=verify_evidence_path,
                evidence_plan_path=evidence_plan_path,
                stages=stages,
                error=output_error,
                exit_code=2,
            )
        evidence_run = run_evidence_file(
            evidence_plan_path,
            output_path=verify_evidence_path,
            force=force,
        )
        stages["evidence_run"] = {
            "exit_code": evidence_run.exit_code,
            "payload": evidence_run.payload,
        }
        if evidence_run.exit_code != 0:
            return _result(
                ok=False,
                goal_id=goal_id,
                goal_path=goal_path,
                evidence_path=verify_evidence_path,
                evidence_plan_path=evidence_plan_path,
                stages=stages,
                error=evidence_run.payload.get("error"),
                exit_code=evidence_run.exit_code,
            )

    stages["evidence"] = {
        "path": verify_evidence_path.as_posix(),
        "source": source,
    }
    goal_verify = verify_goal(goal_path, evidence_path=verify_evidence_path)
    stages["goal_verify"] = {
        "exit_code": goal_verify.exit_code,
        "payload": goal_verify.payload,
    }
    return _result(
        ok=goal_verify.exit_code == 0,
        goal_id=goal_id,
        goal_path=goal_path,
        evidence_path=verify_evidence_path,
        evidence_plan_path=evidence_plan_path,
        stages=stages,
        error=goal_verify.payload.get("error") if goal_verify.exit_code != 0 else None,
        exit_code=goal_verify.exit_code,
    )


def _result(
    *,
    ok: bool,
    goal_id: str | None,
    goal_path: Path,
    evidence_path: Path | None,
    evidence_plan_path: Path | None,
    stages: dict[str, Any],
    error: Any,
    exit_code: int,
) -> GoalVerificationResult:
    payload = {
        "ok": ok,
        "command": "verify.goal",
        "goal_id": goal_id,
        "goal": {"path": goal_path.as_posix()},
        "evidence_plan": (
            {"path": evidence_plan_path.as_posix()} if evidence_plan_path is not None else None
        ),
        "evidence": {"path": evidence_path.as_posix()} if evidence_path is not None else None,
        "stages": stages,
        "error": error,
    }
    return GoalVerificationResult(payload=payload, exit_code=exit_code)


def _lint_stage(report: dict[str, Any], exit_code: int) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "payload": report,
    }


def _trace_stage(contract: dict[str, Any]) -> dict[str, Any]:
    evidence = contract.get("evidence")
    trace_ids: list[str] = []
    if isinstance(evidence, dict) and isinstance(evidence.get("trace_ids"), list):
        trace_ids = [str(item) for item in evidence["trace_ids"]]
    source = contract.get("source") if isinstance(contract.get("source"), dict) else {}
    return {
        "ok": True,
        "mode": "goal_contract_trace_provenance",
        "trace_ids": trace_ids,
        "source": {
            "kind": source.get("kind") if isinstance(source, dict) else None,
            "id": source.get("id") if isinstance(source, dict) else None,
            "path": source.get("path") if isinstance(source, dict) else None,
        },
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Valid GoalContract unexpectedly loaded as non-object.")
    return payload


def _goal_evidence_plan_path(contract: dict[str, Any]) -> str | None:
    evidence = contract.get("evidence")
    if not isinstance(evidence, dict):
        return None
    path = evidence.get("evidence_plan")
    if not isinstance(path, str) or not path.strip():
        return None
    return path.strip()


def _error(code: str, path: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "path": path,
        "message": message,
    }
