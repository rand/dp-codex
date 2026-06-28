from __future__ import annotations

from pathlib import Path

from dp.core.instructions import audit_instructions, inspect_instructions, plan_instruction_update

FIXTURES = Path("tests/fixtures/spec81_projects")


def test_instructions_inspect_discovers_nested_agents() -> None:
    result = inspect_instructions(FIXTURES / "repo_with_nested_agents")
    paths = {item["path"] for item in result.payload["files"]}

    assert result.exit_code == 0
    assert "AGENTS.md" in paths
    assert "service/AGENTS.md" in paths
    root = next(item for item in result.payload["files"] if item["path"] == "AGENTS.md")
    nested = next(item for item in result.payload["files"] if item["path"] == "service/AGENTS.md")
    assert root["precedence"] < nested["precedence"]


def test_instructions_audit_flags_old_dp_guidance() -> None:
    result = audit_instructions(FIXTURES / "repo_with_old_dp_guidance")

    codes = {finding["code"] for finding in result.payload["findings"]}
    assert "instruction_stale_old_dp_command" in codes
    assert result.exit_code == 0


def test_instructions_plan_update_does_not_mutate_agents() -> None:
    root = FIXTURES / "repo_with_root_agents"
    before = (root / "AGENTS.md").read_text(encoding="utf-8")

    result = plan_instruction_update(root)

    after = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert before == after
    assert result.payload["would_mutate"] is False
    assert result.payload["changes"][0]["mode"] == "propose"


def test_instructions_audit_flags_conflicting_skill_and_hook() -> None:
    skill_result = audit_instructions(FIXTURES / "repo_with_conflicting_skills")
    hook_result = audit_instructions(FIXTURES / "repo_with_conflicting_hooks")

    skill_codes = {finding["code"] for finding in skill_result.payload["findings"]}
    hook_codes = {finding["code"] for finding in hook_result.payload["findings"]}
    assert "instruction_skill_contradicts_agents" in skill_codes
    assert "instruction_hook_contradicts_agents" in hook_codes
