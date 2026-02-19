from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_verify_cli_exit_codes_and_json_output(tmp_path: Path, capsys, monkeypatch) -> None:
    verified_manifest = tmp_path / "verified.json"
    _write(tmp_path / "artifacts/proof.txt", "ok")
    _write(
        verified_manifest,
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": True}],
                "artifacts": [{"id": "A1", "path": "artifacts/proof.txt"}],
                "links": [{"truth_id": "T1", "artifact_id": "A1"}],
            }
        ),
    )

    monkeypatch.chdir(tmp_path)
    verified_exit = main(["verify", "--manifest", verified_manifest.as_posix(), "--json"])
    assert verified_exit == 0
    verified_payload = json.loads(capsys.readouterr().out)
    assert verified_payload["outcome"] == "verified"
    assert verified_payload["ok"] is True

    incomplete_manifest = tmp_path / "incomplete.json"
    _write(incomplete_manifest, json.dumps({"truths": [], "artifacts": [], "links": []}))
    incomplete_exit = main(["verify", "--manifest", incomplete_manifest.as_posix(), "--json"])
    assert incomplete_exit == 2
    incomplete_payload = json.loads(capsys.readouterr().out)
    assert incomplete_payload["outcome"] == "incomplete"

    failed_manifest = tmp_path / "failed.json"
    _write(
        failed_manifest,
        json.dumps(
            {
                "truths": [{"id": "T1", "verified": False}],
                "artifacts": [{"id": "A1", "path": "missing.txt"}],
                "links": [{"truth_id": "T1", "artifact_id": "A2"}],
            }
        ),
    )
    failed_exit = main(["verify", "--manifest", failed_manifest.as_posix(), "--json"])
    assert failed_exit == 1
    failed_payload = json.loads(capsys.readouterr().out)
    assert failed_payload["outcome"] == "failed"


def test_verify_cli_text_output(tmp_path: Path, capsys, monkeypatch) -> None:
    manifest = tmp_path / "manifest.json"
    _write(manifest, json.dumps({"truths": [], "artifacts": [], "links": []}))
    monkeypatch.chdir(tmp_path)

    exit_code = main(["verify", "--manifest", manifest.as_posix()])

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "Overall outcome: incomplete" in output
    assert "- truths: incomplete" in output
