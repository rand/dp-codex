from pathlib import Path

import pytest

from dp.core.adr import create_adr, list_adrs, show_adr, update_adr_status


def test_create_adr_uses_conventional_file_naming(tmp_path: Path) -> None:
    directory = tmp_path / "docs/adr"

    record = create_adr("Adopt UV for tooling", directory=directory)

    assert record.adr_id == "ADR-0001"
    assert record.status == "proposal"
    assert Path(record.path).name == "ADR-0001-adopt-uv-for-tooling.md"
    assert Path(record.path).exists()


def test_list_adrs_returns_stable_order(tmp_path: Path) -> None:
    directory = tmp_path / "docs/adr"
    create_adr("First", directory=directory)
    create_adr("Second", directory=directory)

    records = list_adrs(directory)

    assert [record.adr_id for record in records] == ["ADR-0001", "ADR-0002"]


def test_update_adr_status_enforces_lifecycle_rules(tmp_path: Path) -> None:
    directory = tmp_path / "docs/adr"
    created = create_adr("Lifecycle", directory=directory)
    accepted = update_adr_status(created.adr_id, status="accepted", directory=directory)

    assert accepted.status == "accepted"

    with pytest.raises(ValueError, match="Invalid transition accepted -> proposal"):
        update_adr_status(created.adr_id, status="proposal", directory=directory)

    with pytest.raises(ValueError, match="requires --superseded-by"):
        update_adr_status(created.adr_id, status="superseded", directory=directory)

    superseded = update_adr_status(
        created.adr_id,
        status="superseded",
        superseded_by="adr-0002",
        directory=directory,
    )
    assert superseded.status == "superseded"
    assert superseded.superseded_by == "ADR-0002"


def test_show_adr_returns_record_and_content(tmp_path: Path) -> None:
    directory = tmp_path / "docs/adr"
    created = create_adr("Show", directory=directory)

    record, content = show_adr(created.adr_id, directory=directory)

    assert record.adr_id == "ADR-0001"
    assert "## Decision" in content
