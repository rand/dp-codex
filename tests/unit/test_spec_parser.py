from pathlib import Path

from dp.core.spec_parser import SourceLocation, parse_spec_ids


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_spec_ids_returns_stable_ordering_and_deduped_ids(tmp_path: Path) -> None:
    first = tmp_path / "docs/specs/a.md"
    second = tmp_path / "docs/specs/b.md"

    _write(
        first,
        "\n".join(
            (
                "[SPEC-02.01]",
                "[SPEC-01.01]",
                "[SPEC-02.01]",
            )
        ),
    )
    _write(
        second,
        "\n".join(
            (
                "prefix [SPEC-01.01] suffix",
                "[SPEC-03.02] and [SPEC-03.02]",
            )
        ),
    )

    parsed = parse_spec_ids([second, first, second])

    assert [entry.spec_id for entry in parsed] == ["SPEC-01.01", "SPEC-02.01", "SPEC-03.02"]
    assert len(parsed[0].locations) == 2
    assert len(parsed[1].locations) == 2
    assert len(parsed[2].locations) == 2


def test_parse_spec_ids_reports_source_locations(tmp_path: Path) -> None:
    target = tmp_path / "docs/specs/locations.md"
    _write(target, "alpha [SPEC-10.11]\n[SPEC-99.00]\n")

    parsed = parse_spec_ids([target])

    assert parsed[0].spec_id == "SPEC-10.11"
    assert parsed[0].locations == (
        SourceLocation(path=target.as_posix(), line=1, column=8),
    )
    assert parsed[1].spec_id == "SPEC-99.00"
    assert parsed[1].locations == (
        SourceLocation(path=target.as_posix(), line=2, column=2),
    )


def test_parse_spec_ids_ignores_invalid_patterns(tmp_path: Path) -> None:
    target = tmp_path / "docs/specs/invalid.md"
    _write(
        target,
        "\n".join(
            (
                "[SPEC-1.01]",
                "[SPEC-01.1]",
                "[SPEC-AA.BB]",
                "[SPEC-12.34]",
            )
        ),
    )

    parsed = parse_spec_ids([target])

    assert [entry.spec_id for entry in parsed] == ["SPEC-12.34"]
