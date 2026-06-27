from __future__ import annotations

import importlib
import json
from pathlib import Path

from jsonschema import validate

from dp.core.review import ReviewReport

cli_main = importlib.import_module("dp.cli.main")


def test_review_json_output_matches_schema(tmp_path: Path, capsys, monkeypatch) -> None:
    schema = json.loads(Path("docs/schemas/review-output.schema.json").read_text(encoding="utf-8"))
    report = ReviewReport(
        findings=(),
        blocking_count=0,
        advisory_count=0,
        ready_to_commit=True,
    )
    monkeypatch.setattr(cli_main, "run_review", lambda _: report)

    exit_code = cli_main.main(["review", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_verify_json_output_matches_schema(tmp_path: Path, capsys) -> None:
    schema = json.loads(Path("docs/schemas/verify-output.schema.json").read_text(encoding="utf-8"))
    manifest = tmp_path / "manifest.json"
    artifact = tmp_path / "artifacts/proof.txt"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("ok", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [{"id": "A1", "path": "./artifacts/proof.txt"}],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = cli_main.main(["verify", "--manifest", manifest.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_verify_goal_json_output_matches_schema(tmp_path: Path, capsys, monkeypatch) -> None:
    schema = json.loads(Path("docs/schemas/verify-output.schema.json").read_text(encoding="utf-8"))
    goal_payload = json.loads(
        Path("tests/fixtures/goals/valid_spec_70_01.json").read_text(encoding="utf-8")
    )
    goal_payload["evidence"]["evidence_plan"] = "evidence/plan.json"
    (tmp_path / "goal.json").write_text(json.dumps(goal_payload), encoding="utf-8")
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "plan.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "id": "EVIDENCE-SPEC-70.01",
                "goal_id": "GOAL-SPEC-70.01",
                "checks": [
                    {
                        "id": "goal-lint-valid",
                        "kind": "registered_command",
                        "argv": ["dp", "goal", "lint", "goal.json", "--json"],
                        "timeout_seconds": 30,
                        "success_exit_codes": [0],
                        "assertions": [
                            {"type": "exit_code_in", "values": [0]},
                            {"type": "stdout_json"},
                            {"type": "json_path_equals", "path": "$.valid", "value": True},
                        ],
                        "mutation_policy": "read_only",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = cli_main.main(["verify", "--goal", "goal.json", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_goal_lint_json_output_matches_schema(capsys) -> None:
    schema = json.loads(
        Path("docs/schemas/goal-lint-output.schema.json").read_text(encoding="utf-8")
    )

    exit_code = cli_main.main(
        ["goal", "lint", "tests/fixtures/goals/valid_spec_70_01.json", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_evidence_lint_json_output_matches_schema(capsys) -> None:
    schema = json.loads(
        Path("docs/schemas/evidence-lint-output.schema.json").read_text(encoding="utf-8")
    )

    exit_code = cli_main.main(
        ["evidence", "lint", "tests/fixtures/evidence/valid_spec_80_05.json", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_evidence_run_json_output_matches_schema(capsys) -> None:
    schema = json.loads(
        Path("docs/schemas/evidence-run-output.schema.json").read_text(encoding="utf-8")
    )

    exit_code = cli_main.main(
        ["evidence", "run", "tests/fixtures/evidence/valid_run_goal_lint.json", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_loop_lint_json_output_matches_schema(capsys) -> None:
    schema = json.loads(
        Path("docs/schemas/loop-lint-output.schema.json").read_text(encoding="utf-8")
    )

    exit_code = cli_main.main(
        ["loop", "lint", "tests/fixtures/loops/valid_spec_80_04.json", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_lint_json_output_matches_schema(capsys) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-lint-output.schema.json").read_text(encoding="utf-8")
    )

    exit_code = cli_main.main(
        ["campaign", "lint", "tests/fixtures/campaigns/valid_spec_80_06.json", "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_init_json_output_matches_schema(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-init-output.schema.json").read_text(encoding="utf-8")
    )
    primary_spec = tmp_path / "docs/primary/product.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(
        "# Product\n\n## Goals\n\nShip a useful scaffold.\n\n## Evidence\n\nLint artifacts.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = cli_main.main(
        [
            "campaign",
            "init",
            "--primary-spec",
            "docs/primary/product.md",
            "--write",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_refine_json_output_matches_schema(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-refine-output.schema.json").read_text(encoding="utf-8")
    )
    primary_spec = tmp_path / "docs/primary/product.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(
        "# Product\n\n## Requirements\n\nThe CLI must refine campaign artifacts.\n\n"
        "## Evidence\n\nRun campaign lint.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli_main.main(
            [
                "campaign",
                "init",
                "--primary-spec",
                "docs/primary/product.md",
                "--write",
                "--json",
            ]
        )
        == 0
    )
    init_payload = json.loads(capsys.readouterr().out)

    exit_code = cli_main.main(
        ["campaign", "refine", init_payload["artifacts"]["campaign"], "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_run_json_output_matches_schema(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-run-output.schema.json").read_text(encoding="utf-8")
    )
    primary_spec = tmp_path / "docs/primary/product.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(
        "# Product\n\n## Requirements\n\nThe runner must prepare one handoff.\n\n"
        "## Evidence\n\nRun campaign run schema tests.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli_main.main(
            [
                "campaign",
                "init",
                "--primary-spec",
                "docs/primary/product.md",
                "--write",
                "--json",
            ]
        )
        == 0
    )
    init_payload = json.loads(capsys.readouterr().out)

    exit_code = cli_main.main(
        [
            "campaign",
            "run",
            init_payload["artifacts"]["campaign"],
            "--driver",
            "codex",
            "--supervised",
            "--json",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "campaign_not_ready"
    validate(instance=payload, schema=schema)


def test_campaign_ready_json_output_matches_schema(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-ready-output.schema.json").read_text(encoding="utf-8")
    )
    primary_spec = tmp_path / "docs/primary/product.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(
        "# Product\n\n## Requirements\n\nThe campaign must become ready.\n\n"
        "## Evidence\n\nRun campaign ready schema tests.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli_main.main(
            [
                "campaign",
                "init",
                "--primary-spec",
                "docs/primary/product.md",
                "--write",
                "--json",
            ]
        )
        == 0
    )
    init_payload = json.loads(capsys.readouterr().out)

    exit_code = cli_main.main(
        ["campaign", "ready", init_payload["artifacts"]["campaign"], "--json"]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_sync_beads_json_output_matches_schema(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    schema = json.loads(
        Path("docs/schemas/campaign-sync-beads-output.schema.json").read_text(
            encoding="utf-8"
        )
    )
    primary_spec = tmp_path / "docs/primary/product.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(
        "# Product\n\n## Requirements\n\nThe runner must prepare one handoff.\n\n"
        "## Evidence\n\nRun campaign run schema tests.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli_main.main(
            [
                "campaign",
                "init",
                "--primary-spec",
                "docs/primary/product.md",
                "--write",
                "--json",
            ]
        )
        == 0
    )
    init_payload = json.loads(capsys.readouterr().out)

    exit_code = cli_main.main(
        ["campaign", "sync-beads", init_payload["artifacts"]["campaign"], "--json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    validate(instance=payload, schema=schema)


def test_campaign_refine_llm_request_and_response_match_schemas(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    output_schema = json.loads(
        Path("docs/schemas/campaign-refine-output.schema.json").read_text(encoding="utf-8")
    )
    response_schema = json.loads(
        Path("docs/schemas/campaign-refine-llm-response.schema.json").read_text(
            encoding="utf-8"
        )
    )
    primary_spec = tmp_path / "docs/primary/product.md"
    primary_spec.parent.mkdir(parents=True)
    primary_spec.write_text(
        "# Product\n\n## Requirements\n\nThe CLI must refine campaign artifacts.\n\n"
        "## Evidence\n\nRun campaign lint.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli_main.main(
            [
                "campaign",
                "init",
                "--primary-spec",
                "docs/primary/product.md",
                "--write",
                "--json",
            ]
        )
        == 0
    )
    init_payload = json.loads(capsys.readouterr().out)

    assert (
        cli_main.main(
            ["campaign", "refine", init_payload["artifacts"]["campaign"], "--llm", "--json"]
        )
        == 0
    )
    request_payload = json.loads(capsys.readouterr().out)
    validate(instance=request_payload, schema=output_schema)

    campaign = json.loads(Path(init_payload["artifacts"]["campaign"]).read_text(encoding="utf-8"))
    goal_path = Path(campaign["artifacts"]["goals"][0])
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    response = {
        "schema_version": "0.1",
        "campaign_id": request_payload["campaign_id"],
        "prompt_hash": request_payload["request"]["prompt_hash"],
        "provider": "openai",
        "provider_source": "calling_agent",
        "model": "gpt-test",
        "created_at": "2026-06-27T00:00:00Z",
        "nodes": [
            {
                "goal_id": goal["id"],
                "evidence": [
                    {
                        "kind": "registered_command",
                        "argv": ["dp", "goal", "lint", goal_path.as_posix(), "--json"],
                    }
                ],
            }
        ],
    }
    validate(instance=response, schema=response_schema)
