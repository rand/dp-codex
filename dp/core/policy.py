from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

POLICY_MODES = ("strict", "guided", "minimal")
SUPPORTED_CHECKS = (
    "lint",
    "review",
    "task_health",
    "task_sync",
    "tests",
    "trace_coverage",
    "trace_validate",
    "typecheck",
    "verify",
)

POLICY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "dp policy configuration",
    "type": "object",
    "required": ["mode"],
    "properties": {
        "mode": {"type": "string", "enum": list(POLICY_MODES)},
        "overrides": {
            "type": "object",
            "additionalProperties": {"type": "boolean"},
        },
    },
    "additionalProperties": False,
}

BASELINE_BY_MODE = {
    "strict": {check: True for check in SUPPORTED_CHECKS},
    "guided": {
        "lint": True,
        "review": False,
        "task_health": False,
        "task_sync": False,
        "tests": True,
        "trace_coverage": True,
        "trace_validate": True,
        "typecheck": True,
        "verify": False,
    },
    "minimal": {
        "lint": False,
        "review": False,
        "task_health": False,
        "task_sync": False,
        "tests": True,
        "trace_coverage": False,
        "trace_validate": False,
        "typecheck": False,
        "verify": False,
    },
}

_VALIDATOR = Draft202012Validator(POLICY_SCHEMA)


@dataclass(frozen=True)
class PolicyConfig:
    mode: str
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "checks": dict(sorted(self.checks.items())),
        }


def load_policy_config(path: Path) -> PolicyConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Policy file not found: {path.as_posix()}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Policy file is not valid JSON: {path.as_posix()}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Policy file must contain a JSON object.")
    return build_policy_config(payload)


def build_policy_config(payload: dict[str, object]) -> PolicyConfig:
    validate_policy_payload(payload)

    mode = str(payload["mode"])
    overrides_raw = payload.get("overrides", {})
    overrides = dict(overrides_raw) if isinstance(overrides_raw, dict) else {}

    checks = dict(BASELINE_BY_MODE[mode])
    if "task_sync" in overrides and "task_health" not in overrides:
        checks["task_health"] = bool(overrides["task_sync"])
    for key, value in overrides.items():
        checks[str(key)] = bool(value)

    return PolicyConfig(mode=mode, checks=checks)


def validate_policy_payload(payload: dict[str, object]) -> None:
    errors = sorted(_VALIDATOR.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        first = errors[0]
        raise ValueError(f"Policy schema validation failed: {first.message}")

    overrides_raw = payload.get("overrides")
    if overrides_raw is None:
        return
    if not isinstance(overrides_raw, dict):
        raise ValueError("Policy schema validation failed: overrides must be an object.")

    unknown_checks = sorted(check for check in overrides_raw if check not in SUPPORTED_CHECKS)
    if unknown_checks:
        raise ValueError(
            "Unknown policy check override(s): "
            f"{', '.join(unknown_checks)}. Supported checks: {', '.join(SUPPORTED_CHECKS)}."
        )
