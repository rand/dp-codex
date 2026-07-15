from __future__ import annotations

import json
from pathlib import Path

from dp.cli.main import main
from dp.core.skills import skill_templates


def test_skills_scaffold_audit_and_eval(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skills", "scaffold", "--target", "repo", "--json"]) == 0
    scaffold_payload = json.loads(capsys.readouterr().out)
    assert len(scaffold_payload["written"]) == 9
    recovery_skill = (tmp_path / ".agents/skills/dp-failure-recovery/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "repairable_failure" in recovery_skill
    assert "One writer owns one worktree" in recovery_skill
    assert "Verification decides done" in recovery_skill
    assert "Writing helpers require isolated worktrees and disjoint paths" in recovery_skill
    assert "Unavailable consultation is not a blocker" in recovery_skill

    assert main(["skills", "audit", "--json"]) == 0
    audit_payload = json.loads(capsys.readouterr().out)
    assert audit_payload["missing"] == []
    assert audit_payload["ok"] is True

    assert main(["skills", "eval", "--json"]) == 0
    eval_payload = json.loads(capsys.readouterr().out)
    assert eval_payload["ok"] is True
    assert eval_payload["metrics"]["skill_trigger_precision"] == 1.0
    recovery_result = next(
        item for item in eval_payload["results"] if item["expected"] == "dp-failure-recovery"
    )
    assert recovery_result["ok"] is True


def test_checked_in_failure_recovery_skill_matches_scaffold_source() -> None:
    checked_in = Path(".agents/skills/dp-failure-recovery/SKILL.md").read_text(encoding="utf-8")

    assert checked_in == skill_templates()["dp-failure-recovery"]
