from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

FULL_PRIMARY_SPEC = Path("tests/fixtures/primary_specs/scaffold_full.md")


def test_campaign_init_writes_valid_draft_scaffold(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_primary_spec(tmp_path, FULL_PRIMARY_SPEC, "docs/primary/product.md")
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--write", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "campaign.init"
    assert payload["campaign_id"] == "CAMPAIGN-product"
    assert payload["primary_spec"]["sha256"].startswith("sha256:")
    assert payload["needs_refinement"] is True
    assert [section["title"] for section in payload["sections"]] == [
        "Objectives",
        "Requirements",
        "Evidence And Tests",
        "Open Decisions",
    ]

    campaign_path = Path(payload["artifacts"]["campaign"])
    loop_path = Path(payload["artifacts"]["loop"])
    marker_path = Path(payload["artifacts"]["needs_refinement"])
    goal_paths = [Path(path) for path in payload["artifacts"]["goals"]]
    evidence_paths = [Path(path) for path in payload["artifacts"]["evidence_plans"]]
    assert campaign_path.exists()
    assert loop_path.exists()
    assert marker_path.exists()
    assert len(goal_paths) == 4
    assert len(evidence_paths) == 4

    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "draft"
    assert campaign["needs_refinement"]["path"] == marker_path.as_posix()
    assert campaign["primary_spec"]["input_hash"] == payload["primary_spec"]["sha256"]

    assert main(["campaign", "lint", campaign_path.as_posix(), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["loop", "lint", loop_path.as_posix(), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    for goal_path in goal_paths:
        assert main(["goal", "lint", goal_path.as_posix(), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["valid"] is True
    for evidence_path in evidence_paths:
        assert main(["evidence", "lint", evidence_path.as_posix(), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["valid"] is True


def test_campaign_init_sparse_spec_writes_refinement_routes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_primary_spec(
        tmp_path,
        Path("tests/fixtures/primary_specs/scaffold_sparse.md"),
        "docs/primary/sparse.md",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--write", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["needs_refinement"] is True
    assert len(payload["artifacts"]["goals"]) == 1
    routes = {marker["route"] for marker in payload["refinement_markers"]}
    assert "needs_specification" in routes
    assert "needs_validator" in routes

    marker = json.loads(
        Path(payload["artifacts"]["needs_refinement"]).read_text(encoding="utf-8")
    )
    assert marker["needs_refinement"] is True
    assert {item["route"] for item in marker["markers"]} == routes


def test_campaign_init_requires_write(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_primary_spec(tmp_path, FULL_PRIMARY_SPEC, "docs/primary/product.md")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "write_required"
    assert not (tmp_path / "docs/campaigns").exists()


def test_campaign_init_rejects_missing_primary_spec(capsys) -> None:
    exit_code = main(
        ["campaign", "init", "--primary-spec", "docs/primary/missing.md", "--write", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "missing_primary_spec"


def test_campaign_init_does_not_overwrite_changed_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_primary_spec(tmp_path, FULL_PRIMARY_SPEC, "docs/primary/product.md")
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            ["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--write", "--json"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    campaign_path = Path(payload["artifacts"]["campaign"])
    campaign_path.write_text('{"local": "edit"}\n', encoding="utf-8")

    exit_code = main(
        ["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--write", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "artifact_exists"
    assert payload["error"]["path"] == campaign_path.as_posix()


def _copy_primary_spec(tmp_path: Path, source: Path, relative_target: str) -> Path:
    target = tmp_path / relative_target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return Path(relative_target)
