from __future__ import annotations

import argparse
import importlib
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
cli_main = importlib.import_module("dp.cli.main")


# @trace SPEC-82.01
def test_cli_workflow_reference_covers_public_leaf_commands() -> None:
    reference = _read("docs/reference/cli-workflow-reference.md")

    missing = [
        command
        for command in _leaf_commands(cli_main._build_parser())
        if f"`dp {command}" not in reference
    ]

    assert missing == []


# @trace SPEC-82.01
def test_release_readiness_names_current_version_and_scope_boundaries() -> None:
    release = _read("docs/release/v1-readiness.md")
    project = tomllib.loads(_read("pyproject.toml"))["project"]

    assert f"Current package version: `{project['version']}`" in release
    for phrase in (
        "SPEC-80 campaign-control",
        "SPEC-81 agent-experience",
        "CLI-first",
        "MCP remains deferred",
        "plugin packaging remains deferred",
        "background autonomous agent execution remains out of scope",
    ):
        assert phrase in release


# @trace SPEC-82.01
def test_release_readiness_documents_outside_repo_smoke_and_final_gates() -> None:
    release = _read("docs/release/v1-readiness.md")

    for command in (
        "dp --help",
        "dp doctor --json",
        "dp agent bootstrap --json --detail brief",
        "dp agent capabilities --json",
        "make check",
        "dp review --json",
        "dp verify --json",
        "bd --readonly status --json",
    ):
        assert command in release

    assert "outside the dp-codex repository" in release
    assert "Do not publish" in release


def _leaf_commands(parser: argparse.ArgumentParser) -> list[str]:
    return sorted(_walk_leaf_commands(parser, prefix=()))


def _walk_leaf_commands(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> list[str]:
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparsers:
        return [" ".join(prefix)]

    leaves: list[str] = []
    for subparser_action in subparsers:
        for name, child_parser in subparser_action.choices.items():
            leaves.extend(_walk_leaf_commands(child_parser, (*prefix, name)))
    return leaves


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")
