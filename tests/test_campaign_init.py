from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main

FULL_PRIMARY_SPEC = Path("tests/fixtures/primary_specs/scaffold_full.md")
SEMANTIC_PRIMARY_SPEC = Path("tests/fixtures/primary_specs/semantic_signals.md")


# @trace SPEC-80.21
def test_campaign_init_previews_without_write(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_primary_spec(tmp_path, FULL_PRIMARY_SPEC, "docs/primary/product.md")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["write"] is False
    assert payload["written"] is False
    assert payload["preview"] is True
    assert payload["primary_spec"]["kind"] == "local_path"
    assert payload["lint"]["campaign"]["valid"] is True
    assert payload["next_commands"]["write"].endswith("--write --json")
    assert payload["next_commands"]["refine"].endswith("--write --json")
    assert not Path(payload["artifacts"]["campaign"]).exists()
    assert not Path(payload["artifacts"]["loop"]).exists()


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
    assert payload["write"] is True
    assert payload["written"] is True
    assert payload["preview"] is False
    assert payload["primary_spec"]["kind"] == "local_path"
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


def test_campaign_init_extracts_deterministic_semantic_signals(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = _copy_primary_spec(
        tmp_path,
        SEMANTIC_PRIMARY_SPEC,
        "docs/primary/semantic-signals.md",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["campaign", "init", "--primary-spec", primary_spec.as_posix(), "--write", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    compiler = payload["compiler"]
    assert compiler["mode"] == "deterministic_markdown_signals"
    assert compiler["llm"] is False
    assert compiler["semantic_planning"] is False
    assert compiler["ready_for_implementation"] is False
    assert compiler["summary"] == {
        "sections": 4,
        "implementation_candidates": 1,
        "evidence_candidates": 1,
        "decision_nodes": 1,
        "needs_specification": 1,
        "needs_validator": 0,
        "dependency_cues": 2,
    }

    nodes_by_id = {node["section_id"]: node for node in compiler["nodes"]}
    implementation = nodes_by_id["implementation-requirements"]
    assert implementation["classification"] == "implementation"
    assert implementation["refinement_state"] == "implementation_candidate"
    assert any(
        "must compile primary specs" in cue
        for cue in implementation["signals"]["requirements"]
    )
    assert any(
        "Depends on GoalContract lint" in cue
        for cue in implementation["signals"]["dependencies"]
    )

    evidence = nodes_by_id["evidence-and-tests"]
    assert evidence["classification"] == "evidence"
    assert evidence["refinement_state"] == "evidence_candidate"
    assert any(
        "pytest tests/test_campaign_init.py" in cue for cue in evidence["signals"]["evidence"]
    )

    decision = nodes_by_id["open-decisions-and-risks"]
    assert decision["classification"] == "decision"
    assert decision["refinement_state"] == "needs_decision"
    assert "needs_decision" in decision["routes"]

    background = nodes_by_id["background"]
    assert background["classification"] == "context"
    assert background["refinement_state"] == "needs_specification"

    campaign = json.loads(Path(payload["artifacts"]["campaign"]).read_text(encoding="utf-8"))
    assert campaign["state"]["status"] == "draft"
    assert campaign["compiler"]["mode"] == "deterministic_markdown_signals"

    loop = json.loads(Path(payload["artifacts"]["loop"]).read_text(encoding="utf-8"))
    assert loop["nodes"][0]["classification"] == "implementation"
    assert loop["nodes"][0]["depends_on"] == []
    assert loop["nodes"][0]["dependency_cues"]

    goal = json.loads(Path(payload["artifacts"]["goals"][0]).read_text(encoding="utf-8"))
    assert goal["compiler"]["classification"] == "implementation"
    assert goal["compiler"]["refinement_state"] == "implementation_candidate"

    marker = json.loads(
        Path(payload["artifacts"]["needs_refinement"]).read_text(encoding="utf-8")
    )
    assert marker["compiler"]["summary"] == compiler["summary"]
    assert any(item["route"] == "needs_decision" for item in marker["markers"])


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


def test_campaign_init_rejects_url_source_with_stable_diagnostic(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        ["campaign", "init", "--primary-spec", "https://example.test/product.md", "--json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "unsupported_primary_spec_source"
    assert payload["error"]["path"] == "$.primary_spec"
    assert not (tmp_path / "docs/campaigns").exists()


def test_campaign_init_large_spec_preview_is_bounded(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    primary_spec = tmp_path / "docs/primary/large.md"
    primary_spec.parent.mkdir(parents=True, exist_ok=True)
    primary_spec.write_text(
        "# Large Spec\n\n"
        + "\n\n".join(
            f"## Section {index}\n\nThe implementation must support feature {index}. "
            f"Verification uses pytest tests/test_feature_{index}.py."
            for index in range(1, 41)
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["campaign", "init", "--primary-spec", "docs/primary/large.md", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["section_count"] == 40
    assert payload["sections_truncated"] is True
    assert len(payload["sections"]) == 25
    assert payload["compiler"]["node_count"] == 40
    assert payload["compiler"]["nodes_truncated"] is True
    assert len(payload["compiler"]["nodes"]) == 25
    assert payload["artifacts"]["goal_count"] == 40
    assert payload["artifacts"]["evidence_plan_count"] == 40
    assert not Path(payload["artifacts"]["campaign"]).exists()


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
