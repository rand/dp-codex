from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

LevelStatus = Literal["verified", "incomplete", "failed"]
OverallStatus = Literal["verified", "incomplete", "failed"]


@dataclass(frozen=True)
class VerifyLevelResult:
    level: str
    status: LevelStatus
    passed: int
    total: int
    details: tuple[str, ...]

    def to_dict(self) -> dict[str, str | int | list[str]]:
        return {
            "level": self.level,
            "status": self.status,
            "passed": self.passed,
            "total": self.total,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class VerifyReport:
    outcome: OverallStatus
    levels: tuple[VerifyLevelResult, ...]

    def to_dict(self) -> dict[str, str | list[dict[str, str | int | list[str]]]]:
        return {
            "outcome": self.outcome,
            "levels": [level.to_dict() for level in self.levels],
        }


def run_goal_backward_verify(manifest_path: Path) -> VerifyReport:
    payload = _load_manifest(manifest_path)
    truths = payload.get("truths", [])
    artifacts = payload.get("artifacts", [])
    links = payload.get("links", [])

    truth_result, truth_ids = _verify_truths(truths)
    artifact_result, artifact_ids = _verify_artifacts(artifacts, manifest_root=manifest_path.parent)
    link_result = _verify_links(links, truth_ids=truth_ids, artifact_ids=artifact_ids)

    levels = (truth_result, artifact_result, link_result)
    outcome = _rollup_status(levels)
    return VerifyReport(outcome=outcome, levels=levels)


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Manifest file not found: {manifest_path.as_posix()}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {manifest_path.as_posix()}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Verification manifest must be a JSON object.")
    return payload


def _verify_truths(truths: Any) -> tuple[VerifyLevelResult, set[str]]:
    if not isinstance(truths, list) or not truths:
        return (
            VerifyLevelResult(level="truths", status="incomplete", passed=0, total=0, details=()),
            set(),
        )

    details: list[str] = []
    passed = 0
    truth_ids: set[str] = set()

    for index, item in enumerate(truths, start=1):
        if not isinstance(item, dict):
            details.append(f"truth[{index}] is not an object.")
            continue
        truth_id = str(item.get("id", "")).strip()
        if not truth_id:
            details.append(f"truth[{index}] missing id.")
            continue
        truth_ids.add(truth_id)
        if bool(item.get("verified")):
            passed += 1
        else:
            details.append(f"{truth_id} is not verified.")

    status = _derive_level_status(passed=passed, total=len(truths), details=details)
    return (
        VerifyLevelResult(
            level="truths",
            status=status,
            passed=passed,
            total=len(truths),
            details=tuple(details),
        ),
        truth_ids,
    )


def _verify_artifacts(artifacts: Any, manifest_root: Path) -> tuple[VerifyLevelResult, set[str]]:
    if not isinstance(artifacts, list) or not artifacts:
        return (
            VerifyLevelResult(
                level="artifacts",
                status="incomplete",
                passed=0,
                total=0,
                details=(),
            ),
            set(),
        )

    details: list[str] = []
    passed = 0
    artifact_ids: set[str] = set()

    for index, item in enumerate(artifacts, start=1):
        if not isinstance(item, dict):
            details.append(f"artifact[{index}] is not an object.")
            continue
        artifact_id = str(item.get("id", "")).strip()
        path_value = str(item.get("path", "")).strip()
        if not artifact_id:
            details.append(f"artifact[{index}] missing id.")
            continue
        artifact_ids.add(artifact_id)
        if not path_value:
            details.append(f"{artifact_id} missing path.")
            continue
        artifact_path = _resolve_artifact_path(path_value, manifest_root)
        if artifact_path.exists():
            passed += 1
        else:
            details.append(f"{artifact_id} path does not exist: {path_value}")

    status = _derive_level_status(passed=passed, total=len(artifacts), details=details)
    return (
        VerifyLevelResult(
            level="artifacts",
            status=status,
            passed=passed,
            total=len(artifacts),
            details=tuple(details),
        ),
        artifact_ids,
    )


def _verify_links(
    links: Any,
    *,
    truth_ids: set[str],
    artifact_ids: set[str],
) -> VerifyLevelResult:
    if not isinstance(links, list) or not links:
        return VerifyLevelResult(level="links", status="incomplete", passed=0, total=0, details=())

    details: list[str] = []
    passed = 0

    for index, item in enumerate(links, start=1):
        if not isinstance(item, dict):
            details.append(f"link[{index}] is not an object.")
            continue
        truth_id = str(item.get("truth_id") or item.get("truth", "")).strip()
        artifact_id = str(item.get("artifact_id") or item.get("artifact", "")).strip()
        if not truth_id or not artifact_id:
            details.append(f"link[{index}] missing truth_id/artifact_id.")
            continue

        missing: list[str] = []
        if truth_id not in truth_ids:
            missing.append(f"truth '{truth_id}'")
        if artifact_id not in artifact_ids:
            missing.append(f"artifact '{artifact_id}'")

        if missing:
            details.append(f"link[{index}] unresolved: {', '.join(missing)}.")
            continue
        passed += 1

    status = _derive_level_status(passed=passed, total=len(links), details=details)
    return VerifyLevelResult(
        level="links",
        status=status,
        passed=passed,
        total=len(links),
        details=tuple(details),
    )


def _derive_level_status(*, passed: int, total: int, details: list[str]) -> LevelStatus:
    if total == 0:
        return "incomplete"
    if details:
        return "failed"
    if passed == total:
        return "verified"
    return "failed"


def _rollup_status(levels: tuple[VerifyLevelResult, ...]) -> OverallStatus:
    statuses = {level.status for level in levels}
    if "failed" in statuses:
        return "failed"
    if "incomplete" in statuses:
        return "incomplete"
    return "verified"


def _resolve_artifact_path(path_value: str, manifest_root: Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    if path_value.startswith("./") or path_value.startswith("../"):
        return manifest_root / candidate
    return Path.cwd() / candidate
