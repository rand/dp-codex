from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def test_agent_bootstrap_brief_is_enveloped_and_compact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    (tmp_path / "AGENTS.md").write_text("# Agent Instructions\n", encoding="utf-8")
    (tmp_path / "dp-policy.json").write_text('{"mode": "guided"}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["agent", "bootstrap", "--json", "--detail", "brief"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert len(output) <= 2_000
    assert payload["schema_version"] == "dp.response.v1"
    assert payload["affordances"]["phase"] == "orient"
    assert payload["result"]["repo"]["policy_path"] == "dp-policy.json"


def test_agent_capabilities_cli_is_compact(capsys) -> None:
    exit_code = main(["agent", "capabilities", "--json"])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert len(output) <= 5_000
    assert payload["schema_version"] == "dp.capabilities.v1"
