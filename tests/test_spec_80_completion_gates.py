from __future__ import annotations

from pathlib import Path


# @trace SPEC-80.22
def test_spec_80_completion_gates_include_required_experience_work() -> None:
    spec = Path("docs/specs/SPEC-80-22-end-to-end-agent-experience-completion-gates.md").read_text(
        encoding="utf-8"
    )
    execution_plan = Path("docs/EXECUTION-PLAN.md").read_text(encoding="utf-8")
    parent_spec = Path("docs/specs/SPEC-80-agent-campaign-control-plane-for-dp-codex.md").read_text(
        encoding="utf-8"
    )

    required_ids = ["dpcx-ea9.1", "dpcx-ea9.2", "dpcx-ea9.3", "dpcx-ea9.4", "dpcx-ea9.5"]
    for issue_id in required_ids:
        assert issue_id in spec

    required_phrases = [
        "current Beads claim/intake ergonomics",
        "repo-scoped Codex hook/config guidance",
        "verification evidence stronger than file existence",
        "flow pilots and friction metrics",
        "ADR-quality decision",
        (
            "primary-spec intake tested against both concise roadmap specs and large "
            "architecture/system specs"
        ),
    ]
    for phrase in required_phrases:
        assert phrase in parent_spec

    assert (
        "M7-derived end-to-end agent experience gates required for SPEC-80 closure"
        in execution_plan
    )
