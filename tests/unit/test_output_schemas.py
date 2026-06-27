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
