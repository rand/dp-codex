import pytest

from dp.core.task_normalization import normalize_priority, normalize_status


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("open", "open"),
        ("todo", "open"),
        ("in-progress", "in_progress"),
        ("in progress", "in_progress"),
        ("done", "closed"),
        ("snoozed", "deferred"),
    ],
)
def test_normalize_status_accepts_canonical_and_aliases(input_value: str, expected: str) -> None:
    assert normalize_status(input_value) == expected


def test_normalize_status_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Invalid status value 'unknown'"):
        normalize_status("unknown")


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("0", "P0"),
        ("2", "P2"),
        ("p4", "P4"),
        ("P1", "P1"),
    ],
)
def test_normalize_priority_accepts_numeric_and_p_notation(input_value: str, expected: str) -> None:
    assert normalize_priority(input_value) == expected


def test_normalize_priority_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Invalid priority value 'P9'"):
        normalize_priority("P9")
