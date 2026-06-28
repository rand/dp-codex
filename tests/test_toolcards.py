from __future__ import annotations

import json

from dp.core.toolcards import capabilities_payload


def test_capabilities_expose_toolcards_and_schema_versions() -> None:
    payload = capabilities_payload()

    assert payload["schema_version"] == "dp.capabilities.v1"
    assert payload["schemas"]["response"] == "dp.response.v1"
    names = {card["name"] for card in payload["toolcards"]}
    assert "dp loop next" in names
    assert "dp agent bootstrap" in names


def test_toolcards_are_compact_enough_for_agent_discovery() -> None:
    encoded = json.dumps(capabilities_payload(), sort_keys=True)

    assert len(encoded) <= 5_000
    for card in capabilities_payload()["toolcards"]:
        assert card["output_schema"] == "dp.response.v1"
        assert {"phase", "mutability", "cost", "common_next"} <= set(card)
