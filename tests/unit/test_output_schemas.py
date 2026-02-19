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
