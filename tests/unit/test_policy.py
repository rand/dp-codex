from __future__ import annotations

import json
from pathlib import Path

import pytest

from dp.core.policy import build_policy_config, load_policy_config


def test_build_policy_config_applies_mode_and_overrides() -> None:
    config = build_policy_config(
        {
            "mode": "guided",
            "overrides": {
                "review": True,
                "verify": True,
            },
        }
    )

    assert config.mode == "guided"
    assert config.checks["review"] is True
    assert config.checks["verify"] is True
    assert config.checks["tests"] is True


def test_build_policy_config_rejects_unknown_override_checks() -> None:
    with pytest.raises(ValueError, match="Unknown policy check override"):
        build_policy_config({"mode": "strict", "overrides": {"unknown_check": True}})


def test_load_policy_config_from_file(tmp_path: Path) -> None:
    target = tmp_path / "policy.json"
    target.write_text(
        json.dumps(
            {
                "mode": "minimal",
                "overrides": {"lint": True},
            }
        ),
        encoding="utf-8",
    )

    config = load_policy_config(target)

    assert config.mode == "minimal"
    assert config.checks["lint"] is True
