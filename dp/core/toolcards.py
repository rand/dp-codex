from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dp.core.agent_response import cost

CAPABILITIES_SCHEMA_VERSION = "dp.capabilities.v1"


@dataclass(frozen=True)
class ToolCard:
    name: str
    purpose: str
    phase: str
    output_schema: str
    mutability: str
    idempotent: bool
    destructive: bool
    open_world: bool
    requires_trust: bool
    cost: dict[str, Any]
    common_next: tuple[str, ...]
    detail_modes: tuple[str, ...] = ("brief", "normal", "full")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "phase": self.phase,
            "output_schema": self.output_schema,
            "mutability": self.mutability,
            "idempotent": self.idempotent,
            "destructive": self.destructive,
            "open_world": self.open_world,
            "requires_trust": self.requires_trust,
            "cost": self.cost,
            "common_next": list(self.common_next),
        }


def all_toolcards() -> list[dict[str, Any]]:
    return [card.to_dict() for card in TOOLCARDS]


def capabilities_payload() -> dict[str, Any]:
    return {
        "schema_version": CAPABILITIES_SCHEMA_VERSION,
        "toolcards": all_toolcards(),
        "schemas": {
            "response": "dp.response.v1",
            "hint": "dp.explain.v1",
            "goal": "GoalContract/0.1",
            "evidence": "EvidencePlan/0.1",
            "loop": "LoopLedger/0.1",
            "campaign": "CampaignManifest/0.1",
        },
        "detail_modes": ["brief", "normal", "full"],
    }


def _card(
    name: str,
    purpose: str,
    phase: str,
    mutability: str,
    *,
    idempotent: bool,
    common_next: tuple[str, ...],
    tokens: str = "low",
    executes_commands: bool = False,
    requires_trust: bool = False,
) -> ToolCard:
    return ToolCard(
        name=name,
        purpose=purpose,
        phase=phase,
        output_schema="dp.response.v1",
        mutability=mutability,
        idempotent=idempotent,
        destructive=False,
        open_world=False,
        requires_trust=requires_trust,
        cost=cost(tokens=tokens, executes_commands=executes_commands),
        common_next=common_next,
    )


TOOLCARDS: tuple[ToolCard, ...] = (
    _card(
        "dp agent bootstrap",
        "Orient an agent in the current repo.",
        "orient",
        "read_only",
        idempotent=True,
        common_next=("dp instructions audit", "dp agent capabilities", "dp adopt inspect"),
    ),
    _card(
        "dp agent capabilities",
        "Expose compact command metadata.",
        "discover",
        "read_only",
        idempotent=True,
        common_next=("dp explain", "dp agent bootstrap"),
    ),
    _card(
        "dp explain",
        "Explain a stable hint or error code.",
        "repair",
        "read_only",
        idempotent=True,
        common_next=("dp agent bootstrap",),
    ),
    _card(
        "dp instructions inspect",
        "Discover local instruction files and precedence.",
        "orient",
        "read_only",
        idempotent=True,
        common_next=("dp instructions audit", "dp instructions plan-update"),
    ),
    _card(
        "dp instructions audit",
        "Find instruction conflicts without mutating files.",
        "verify",
        "read_only",
        idempotent=True,
        common_next=("dp instructions plan-update",),
    ),
    _card(
        "dp adopt inspect",
        "Classify current dp adoption state.",
        "adopt",
        "read_only",
        idempotent=True,
        common_next=("dp adopt plan", "dp instructions audit"),
    ),
    _card(
        "dp adopt plan",
        "Write an additive adoption plan.",
        "adopt",
        "writes_project_artifacts",
        idempotent=False,
        common_next=("dp adopt apply", "dp adopt verify"),
        tokens="medium",
    ),
    _card(
        "dp campaign status",
        "Recover campaign state and next safe action.",
        "recover",
        "read_only",
        idempotent=True,
        common_next=("dp campaign run", "dp loop next"),
        tokens="medium",
    ),
    _card(
        "dp loop next",
        "Return the next ready goal and optional Codex handoff.",
        "claim",
        "writes_dp_state",
        idempotent=False,
        common_next=("dp goal start", "dp goal block", "dp goal release"),
        tokens="medium",
    ),
    _card(
        "dp goal status",
        "Read append-only goal lifecycle state.",
        "work",
        "read_only",
        idempotent=True,
        common_next=("dp goal start", "dp evidence run", "dp goal verify"),
    ),
    _card(
        "dp evidence run",
        "Run deterministic registered checks from an EvidencePlan.",
        "verify",
        "runs_registered_checks",
        idempotent=False,
        common_next=("dp goal verify", "dp explain"),
        tokens="medium",
        executes_commands=True,
    ),
    _card(
        "dp hooks audit",
        "Audit local hooks.",
        "verify",
        "read_only",
        idempotent=True,
        common_next=("dp hooks doctor", "dp hooks scaffold"),
    ),
)
