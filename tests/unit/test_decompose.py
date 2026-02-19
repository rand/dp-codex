import pytest

from dp.core.decompose import decompose_items, resolve_context_window


def test_decompose_items_generates_dag_plan() -> None:
    plan = decompose_items(["Implement parser", "Add tests"], context_window=4096)

    assert plan.is_dag is True
    assert [node.node_id for node in plan.nodes] == ["T1", "T2"]
    assert plan.nodes[1].depends_on == ("T1",)


def test_decompose_items_splits_large_work_by_context_window() -> None:
    long_item = " ".join(["token"] * 128)
    plan = decompose_items([long_item], context_window=300)

    assert len(plan.nodes) > 1
    assert all(node.estimated_tokens <= 300 for node in plan.nodes)


def test_decompose_items_rejects_non_positive_context_window() -> None:
    with pytest.raises(ValueError, match="context_window must be greater than 0"):
        decompose_items(["Implement parser"], context_window=0)


def test_resolve_context_window_uses_codex_presets() -> None:
    assert resolve_context_window(None, "codex-small") == 32000
    assert resolve_context_window(None, "codex-medium") == 64000
    assert resolve_context_window(None, "codex-large") == 128000


def test_codex_preset_calibration_changes_split_behavior() -> None:
    representative_item = " ".join(["token"] * 5000)
    small_plan = decompose_items(
        [representative_item],
        context_window=resolve_context_window(None, "codex-small"),
    )
    large_plan = decompose_items(
        [representative_item],
        context_window=resolve_context_window(None, "codex-large"),
    )

    assert len(small_plan.nodes) >= len(large_plan.nodes)
