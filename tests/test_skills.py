from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main


def test_skills_scaffold_audit_and_eval(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skills", "scaffold", "--target", "repo", "--json"]) == 0
    scaffold_payload = json.loads(capsys.readouterr().out)
    assert len(scaffold_payload["written"]) == 8

    assert main(["skills", "audit", "--json"]) == 0
    audit_payload = json.loads(capsys.readouterr().out)
    assert audit_payload["missing"] == []
    assert audit_payload["ok"] is True

    assert main(["skills", "eval", "--json"]) == 0
    eval_payload = json.loads(capsys.readouterr().out)
    assert eval_payload["ok"] is True
    assert eval_payload["metrics"]["skill_trigger_precision"] == 1.0
