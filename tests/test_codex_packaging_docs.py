from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# @trace SPEC-70.06
def test_spec70_06_packaging_decision_is_documented() -> None:
    spec = _read("docs/specs/SPEC-70-06-codex-packaging.md")
    adr = _read("docs/adr/ADR-0014-codex-packaging-stays-cli-first.md")
    runbook = _read("docs/runbooks/codex-packaging.md")

    combined = "\n".join([spec, adr, runbook])
    for required in (
        "CLI-first",
        "Repo-local Codex skill",
        "MCP",
        "plugin",
        "hooks",
        "no network dependency",
        "no LLM calls",
    ):
        assert required in combined

    assert "| CLI + `AGENTS.md` |" in spec
    assert "| MCP server |" in spec
    assert "| Codex plugin |" in spec
    assert "Ship an MCP server now" in adr
    assert "Ship a Codex plugin now" in adr
    assert "When to Consider MCP" in runbook
    assert "When to Consider a Plugin" in runbook


# @trace SPEC-70.06
def test_dp_campaign_control_skill_is_safe_cli_scaffold() -> None:
    skill = _read(".agents/skills/dp-campaign-control/SKILL.md")
    metadata = _frontmatter(skill)

    assert metadata["name"] == "dp-campaign-control"
    assert "dp-codex-aware repositories" in metadata["description"]
    assert "SPEC-80-style campaign" in metadata["description"]

    for command in (
        "dp doctor --json",
        "dp task claim --json",
        "dp campaign recover",
        "dp campaign run",
        "dp goal start",
        "dp evidence run",
        "dp verify --goal",
        "dp goal block",
        "dp campaign sync-beads",
    ):
        assert command in skill

    for invariant in (
        "Do not mark completion from agent narration",
        "Do not execute raw shell from generated JSON",
        "Do not call an LLM from hooks, validators, evidence assertions, or CI",
        "Do not spawn Codex from dp in this workflow",
    ):
        assert invariant in skill


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _frontmatter(markdown: str) -> dict[str, str]:
    assert markdown.startswith("---\n")
    end = markdown.index("\n---\n", 4)
    fields: dict[str, str] = {}
    for line in markdown[4:end].splitlines():
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields
