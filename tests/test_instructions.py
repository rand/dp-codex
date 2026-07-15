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
    preview = result.payload["changes"][0]["patch_preview"]
    assert "## Recovery and Escalation" in preview
    assert "## Agent Collaboration" in preview


def test_instructions_audit_flags_missing_recovery_and_collaboration_discipline() -> None:
    result = audit_instructions(FIXTURES / "repo_with_root_agents")

    codes = {finding["code"] for finding in result.payload["findings"]}
    assert "instruction_missing_recovery_discipline" in codes
    assert "instruction_missing_collaboration_discipline" in codes
    assert any(
        hint["code"] == "DP-HINT-INSTRUCTIONS-DISCIPLINE-MISSING"
        for hint in result.payload["hints"]
    )


def test_instructions_audit_rejects_empty_discipline_headings(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# Agent Instructions\n\n"
        "Run `dp agent bootstrap --json --detail brief`.\n\n"
        "## Recovery and Escalation\n\n"
        "Investigate failures.\n\n"
        "## Agent Collaboration\n\n"
        "Ask for help.\n",
        encoding="utf-8",
    )

    result = audit_instructions(tmp_path)
    codes = {finding["code"] for finding in result.payload["findings"]}

    assert "instruction_missing_recovery_discipline" in codes
    assert "instruction_missing_collaboration_discipline" in codes


def test_nested_discipline_does_not_satisfy_effective_root_scope(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Root\n", encoding="utf-8")
    nested = tmp_path / "service/AGENTS.md"
    nested.parent.mkdir()
    nested.write_text(
        "# Nested\n\n<!-- dp-agent-discipline:v1 -->\n\n"
        "Run `dp agent bootstrap --json --detail brief`.\n",
        encoding="utf-8",
    )

    result = audit_instructions(tmp_path)
    codes = {finding["code"] for finding in result.payload["findings"]}

    assert "instruction_missing_bootstrap" in codes
    assert "instruction_missing_recovery_discipline" in codes
    assert "instruction_missing_collaboration_discipline" in codes


def test_root_override_is_the_effective_instruction_scope(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# Root\n\n<!-- dp-agent-discipline:v1 -->\n\n"
        "Run `dp agent bootstrap --json --detail brief`.\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.override.md").write_text("# Effective override\n", encoding="utf-8")

    audit = audit_instructions(tmp_path)
    plan = plan_instruction_update(tmp_path)
    codes = {finding["code"] for finding in audit.payload["findings"]}

    assert "instruction_missing_bootstrap" in codes
    assert "instruction_missing_recovery_discipline" in codes
    assert "instruction_missing_collaboration_discipline" in codes
    assert plan.payload["target"] == "AGENTS.override.md"


def test_discipline_marker_without_managed_body_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# Root\n\n<!-- dp-agent-discipline:v1 -->\n\n"
        "Run `dp agent bootstrap --json --detail brief`.\n",
        encoding="utf-8",
    )

    result = audit_instructions(tmp_path)
    codes = {finding["code"] for finding in result.payload["findings"]}

    assert "instruction_missing_recovery_discipline" in codes
    assert "instruction_missing_collaboration_discipline" in codes


def test_complete_managed_discipline_prevents_duplicate_sections(tmp_path: Path) -> None:
    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        "# Root\n\nRun `dp agent bootstrap --json --detail brief`.\n",
        encoding="utf-8",
    )
    initial = plan_instruction_update(tmp_path)
    preview = initial.payload["changes"][0]["patch_preview"]
    agents_path.write_text(agents_path.read_text(encoding="utf-8") + preview, encoding="utf-8")

    result = plan_instruction_update(tmp_path)

    assert result.payload["changes"] == []


def test_instructions_audit_flags_conflicting_skill_and_hook() -> None:
    skill_result = audit_instructions(FIXTURES / "repo_with_conflicting_skills")
    hook_result = audit_instructions(FIXTURES / "repo_with_conflicting_hooks")

    skill_codes = {finding["code"] for finding in skill_result.payload["findings"]}
    hook_codes = {finding["code"] for finding in hook_result.payload["findings"]}
    assert "instruction_skill_contradicts_agents" in skill_codes
    assert "instruction_hook_contradicts_agents" in hook_codes
