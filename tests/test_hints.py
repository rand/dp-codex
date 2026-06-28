from __future__ import annotations

from dp.core.hints import explain_code, hint_payload


def test_explain_known_hint_code() -> None:
    payload, exit_code = explain_code("DP-HINT-EVIDENCE-MISSING")

    assert exit_code == 0
    assert payload["schema_version"] == "dp.explain.v1"
    assert payload["severity"] == "error"
    assert payload["next_actions"][0]["command"].startswith("dp goal block")


def test_explain_common_error_code_alias() -> None:
    payload, exit_code = explain_code("missing_evidence_path")

    assert exit_code == 0
    assert payload["code"] == "DP-HINT-EVIDENCE-MISSING"


def test_hint_payload_includes_explain_command() -> None:
    payload = hint_payload("DP-HINT-LOOP-NO-READY-NODES")

    assert payload["explain_command"] == "dp explain DP-HINT-LOOP-NO-READY-NODES --json"
