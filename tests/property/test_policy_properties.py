from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from dp.core.policy import (
    BASELINE_BY_MODE,
    POLICY_MODES,
    SUPPORTED_CHECKS,
    build_policy_config,
)


@given(
    mode=st.sampled_from(POLICY_MODES),
    overrides=st.dictionaries(
        keys=st.sampled_from(SUPPORTED_CHECKS),
        values=st.booleans(),
        max_size=len(SUPPORTED_CHECKS),
    ),
)
def test_build_policy_config_merges_mode_and_overrides_property(
    mode: str,
    overrides: dict[str, bool],
) -> None:
    config = build_policy_config({"mode": mode, "overrides": overrides})

    expected_checks = dict(BASELINE_BY_MODE[mode])
    if "task_sync" in overrides and "task_health" not in overrides:
        expected_checks["task_health"] = overrides["task_sync"]
    expected_checks.update(overrides)
    assert config.mode == mode
    assert config.checks == expected_checks


@given(
    mode=st.sampled_from(POLICY_MODES),
    unknown_check=st.from_regex(r"[a-z_]{1,20}", fullmatch=True),
)
def test_build_policy_config_rejects_unknown_override_property(
    mode: str,
    unknown_check: str,
) -> None:
    assume(unknown_check not in SUPPORTED_CHECKS)

    with pytest.raises(ValueError, match="Unknown policy check override"):
        build_policy_config(
            {
                "mode": mode,
                "overrides": {unknown_check: True},
            }
        )
