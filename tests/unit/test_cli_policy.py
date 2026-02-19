from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_policy_validate_cli_json_output(tmp_path: Path, capsys) -> None:
    policy_path = tmp_path / "policy.json"
    _write(
        policy_path,
        json.dumps(
            {
                "mode": "guided",
                "overrides": {"review": True},
            }
        ),
    )

    exit_code = main(["policy", "validate", "--config", policy_path.as_posix(), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["policy"]["checks"]["review"] is True


def test_policy_validate_cli_invalid_config(tmp_path: Path, capsys) -> None:
    policy_path = tmp_path / "policy.json"
    _write(policy_path, json.dumps({"mode": "invalid"}))

    exit_code = main(["policy", "validate", "--config", policy_path.as_posix(), "--json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
