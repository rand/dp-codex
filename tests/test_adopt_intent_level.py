from __future__ import annotations

from pathlib import Path
from typing import Any

from dp.core.adoption import inspect_adoption
from dp.core.goal_lint import intent_enforcement_active

SPEC81_SURFACE = (
    "docs/reference/agent-response-contract.md",
    "docs/reference/toolcards.md",
    "docs/reference/hint-codes.md",
)
INTENT_MARKER = "docs/reference/intent-graph.md"


def _write_spec81_repo(tmp_path: Path) -> None:
    for path in SPEC81_SURFACE:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Reference\n", encoding="utf-8")


def _spec83_level(payload: dict[str, Any]) -> dict[str, Any]:
    return next(level for level in payload["levels"] if level["id"] == "spec83")


def test_spec81_repo_without_marker_stays_below_the_intent_graph_level(
    tmp_path: Path,
) -> None:
    _write_spec81_repo(tmp_path)

    payload = inspect_adoption(tmp_path).payload

    assert payload["classification"] == "current_spec81"
    assert payload["signals"]["has_spec83"] is False
    assert payload["signals"]["missing_spec83_structures"] == [INTENT_MARKER]
    assert _spec83_level(payload)["adopted"] is False


def test_intent_graph_marker_advances_classification_to_spec83(tmp_path: Path) -> None:
    _write_spec81_repo(tmp_path)
    (tmp_path / INTENT_MARKER).write_text("# Intent Graph\n", encoding="utf-8")

    payload = inspect_adoption(tmp_path).payload

    assert payload["classification"] == "current_spec83"
    assert payload["signals"]["has_spec83"] is True
    assert payload["signals"]["missing_spec83_structures"] == []
    assert _spec83_level(payload)["adopted"] is True


def test_adopt_inspect_describes_the_intent_graph_level_delta(tmp_path: Path) -> None:
    _write_spec81_repo(tmp_path)

    level = _spec83_level(inspect_adoption(tmp_path).payload)

    assert level["classification"] == "current_spec83"
    assert level["marker"] == INTENT_MARKER
    assert "Intent-graph enforcement" in level["delta"]
    assert "outcome" in level["delta"]
    assert "Work serves intent" in level["delta"]


def test_marker_without_spec81_surface_does_not_claim_spec83(tmp_path: Path) -> None:
    (tmp_path / "docs/reference").mkdir(parents=True)
    (tmp_path / INTENT_MARKER).write_text("# Intent Graph\n", encoding="utf-8")

    payload = inspect_adoption(tmp_path).payload

    assert payload["classification"] != "current_spec83"
    assert payload["signals"]["has_spec83"] is False


def test_lint_enforcement_agrees_with_spec83_classification(tmp_path: Path) -> None:
    """intent_enforcement_active and has_spec83 use the same predicate."""
    marker_only = tmp_path / "marker-only"
    (marker_only / "docs/reference").mkdir(parents=True)
    (marker_only / INTENT_MARKER).write_text("# Intent Graph\n", encoding="utf-8")

    full = tmp_path / "full"
    full.mkdir()
    _write_spec81_repo(full)
    (full / INTENT_MARKER).write_text("# Intent Graph\n", encoding="utf-8")

    for repo in (marker_only, full):
        signals = inspect_adoption(repo).payload["signals"]
        assert intent_enforcement_active(repo) is signals["has_spec83"]

    assert intent_enforcement_active(marker_only) is False
    assert intent_enforcement_active(full) is True
