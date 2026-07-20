from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dp.cli.main import main

SOURCE_GOAL = Path(__file__).parent / "fixtures/goals/valid_spec_70_01.json"
REPEATED_BLOCK_HINT = "DP-HINT-GOAL-REPEATED-BLOCKS"


def _setup(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / "goal.json").write_text(
        SOURCE_GOAL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)


def _block(capsys: Any) -> dict[str, Any]:
    exit_code = main(["goal", "block", "goal.json", "--reason", "needs_decision", "--json"])
    assert exit_code == 0
    return json.loads(capsys.readouterr().out)


def _claim(capsys: Any) -> None:
    assert main(["goal", "claim", "goal.json", "--agent", "codex", "--json"]) == 0
    capsys.readouterr()


def _hint_codes(payload: dict[str, Any]) -> set[str]:
    return {hint["code"] for hint in payload.get("hints", [])}


def test_first_block_since_claim_carries_no_repeated_block_hint(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _setup(tmp_path, monkeypatch)
    _claim(capsys)

    payload = _block(capsys)

    assert payload["blocks_since_claim"] == 1
    assert REPEATED_BLOCK_HINT not in _hint_codes(payload)


def test_second_block_since_claim_requires_owner_words_restatement_hint(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _setup(tmp_path, monkeypatch)
    _claim(capsys)
    _block(capsys)

    payload = _block(capsys)

    assert payload["ok"] is True
    assert payload["blocks_since_claim"] == 2
    assert REPEATED_BLOCK_HINT in _hint_codes(payload)
    hint = next(h for h in payload["hints"] if h["code"] == REPEATED_BLOCK_HINT)
    assert "restate, in the owner's words" in hint["message"]

    assert main(["goal", "status", "goal.json", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert REPEATED_BLOCK_HINT in _hint_codes(status)


def test_reclaiming_resets_the_repeated_block_counter(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    _setup(tmp_path, monkeypatch)
    _claim(capsys)
    _block(capsys)
    _block(capsys)
    _claim(capsys)

    payload = _block(capsys)

    assert payload["blocks_since_claim"] == 1
    assert REPEATED_BLOCK_HINT not in _hint_codes(payload)
