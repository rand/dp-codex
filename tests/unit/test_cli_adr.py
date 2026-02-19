from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def test_adr_cli_lifecycle_commands(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    create_exit = main(["adr", "create", "Adopt ADR workflow"])
    assert create_exit == 0
    assert "Created ADR-0001" in capsys.readouterr().out

    list_exit = main(["adr", "list"])
    assert list_exit == 0
    assert "ADR-0001 proposal Adopt ADR workflow" in capsys.readouterr().out

    accept_exit = main(["adr", "update", "ADR-0001", "--status", "accepted"])
    assert accept_exit == 0
    assert "Updated ADR-0001 -> accepted" in capsys.readouterr().out

    supersede_missing_exit = main(["adr", "update", "ADR-0001", "--status", "superseded"])
    assert supersede_missing_exit == 2
    assert "requires --superseded-by" in capsys.readouterr().err

    supersede_exit = main(
        ["adr", "update", "ADR-0001", "--status", "superseded", "--superseded-by", "ADR-0002"]
    )
    assert supersede_exit == 0
    assert "Updated ADR-0001 -> superseded" in capsys.readouterr().out


def test_adr_cli_json_outputs(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    create_exit = main(["adr", "create", "JSON ADR", "--json"])
    assert create_exit == 0
    create_payload = json.loads(capsys.readouterr().out)
    assert create_payload["ok"] is True
    assert create_payload["adr"]["id"] == "ADR-0001"

    show_exit = main(["adr", "show", "ADR-0001", "--json"])
    assert show_exit == 0
    show_payload = json.loads(capsys.readouterr().out)
    assert show_payload["ok"] is True
    assert show_payload["adr"]["status"] == "proposal"
    assert "## Context" in show_payload["content"]
