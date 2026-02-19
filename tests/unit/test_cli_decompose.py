from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_decompose_cli_json_with_items(capsys) -> None:
    exit_code = main(
        [
            "decompose",
            "--item",
            "Implement parser module",
            "--item",
            "Write integration tests",
            "--context-window",
            "512",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["context_window"] == 512
    assert len(payload["nodes"]) == 2


def test_decompose_cli_uses_spec_ids_when_items_not_provided(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _write(tmp_path / "docs/specs/spec.md", "[SPEC-01.01]\n[SPEC-02.02]")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["decompose", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert len(payload["nodes"]) >= 1
    combined_titles = " ".join(node["title"] for node in payload["nodes"])
    assert "SPEC-01.01" in combined_titles
    assert "SPEC-02.02" in combined_titles


def test_decompose_cli_fails_without_items_or_specs(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["decompose", "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_decompose_cli_supports_codex_preset(capsys) -> None:
    exit_code = main(
        [
            "decompose",
            "--item",
            "Implement parser",
            "--preset",
            "codex-medium",
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["context_window"] == 64000
