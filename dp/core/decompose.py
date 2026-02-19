from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

CODEX_CONTEXT_PRESETS = {
    "codex-small": 32000,
    "codex-medium": 64000,
    "codex-large": 128000,
}
DEFAULT_CODEX_PRESET = "codex-small"


@dataclass(frozen=True)
class DecomposeNode:
    node_id: str
    title: str
    estimated_tokens: int
    depends_on: tuple[str, ...]

    def to_dict(self) -> dict[str, str | int | list[str]]:
        return {
            "id": self.node_id,
            "title": self.title,
            "estimated_tokens": self.estimated_tokens,
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class DecomposePlan:
    context_window: int
    nodes: tuple[DecomposeNode, ...]
    is_dag: bool

    def to_dict(self) -> dict[str, int | bool | list[dict[str, str | int | list[str]]]]:
        return {
            "context_window": self.context_window,
            "is_dag": self.is_dag,
            "nodes": [node.to_dict() for node in self.nodes],
        }


def decompose_items(items: Iterable[str], context_window: int) -> DecomposePlan:
    if context_window <= 0:
        raise ValueError("context_window must be greater than 0.")

    normalized_items = _apply_merge_heuristic(
        [item.strip() for item in items if item.strip()],
        context_window=context_window,
    )
    nodes: list[DecomposeNode] = []
    previous_node: str | None = None

    for index, item in enumerate(normalized_items, start=1):
        estimated_tokens = _estimate_tokens(item)
        chunk_count = max(1, math.ceil(estimated_tokens / context_window))
        remaining = estimated_tokens

        for chunk_index in range(1, chunk_count + 1):
            node_id = f"T{index}" if chunk_count == 1 else f"T{index}.{chunk_index}"
            title = item
            if chunk_count > 1:
                title = f"{item} (part {chunk_index}/{chunk_count})"

            chunk_tokens = min(context_window, remaining)
            remaining -= chunk_tokens
            dependencies = (previous_node,) if previous_node else ()
            node = DecomposeNode(
                node_id=node_id,
                title=title,
                estimated_tokens=chunk_tokens,
                depends_on=dependencies,
            )
            nodes.append(node)
            previous_node = node_id

    plan = DecomposePlan(
        context_window=context_window,
        nodes=tuple(nodes),
        is_dag=_is_dag(nodes),
    )
    return plan


def resolve_context_window(context_window: int | None, preset: str | None) -> int:
    if context_window is not None:
        if context_window <= 0:
            raise ValueError("context_window must be greater than 0.")
        return context_window

    selected = (preset or DEFAULT_CODEX_PRESET).strip().lower()
    if selected not in CODEX_CONTEXT_PRESETS:
        raise ValueError(
            f"Unknown context preset '{selected}'. "
            f"Use one of: {', '.join(sorted(CODEX_CONTEXT_PRESETS))}."
        )
    return CODEX_CONTEXT_PRESETS[selected]


def _estimate_tokens(item: str) -> int:
    words = len(item.split())
    return max(256, words * 36)


def _apply_merge_heuristic(items: list[str], context_window: int) -> list[str]:
    if not items:
        return []

    threshold = max(192, context_window // 20)
    merged: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0

    for item in items:
        tokens = _estimate_tokens(item)
        if tokens >= threshold:
            if buffer:
                merged.append(" + ".join(buffer))
                buffer = []
                buffer_tokens = 0
            merged.append(item)
            continue

        buffer.append(item)
        buffer_tokens += tokens
        if buffer_tokens >= threshold:
            merged.append(" + ".join(buffer))
            buffer = []
            buffer_tokens = 0

    if buffer:
        merged.append(" + ".join(buffer))

    return merged


def _is_dag(nodes: list[DecomposeNode]) -> bool:
    graph = {node.node_id: set(node.depends_on) for node in nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visited:
            return True
        if node_id in visiting:
            return False
        visiting.add(node_id)
        for dependency in graph.get(node_id, set()):
            if dependency not in graph:
                continue
            if not visit(dependency):
                return False
        visiting.remove(node_id)
        visited.add(node_id)
        return True

    return all(visit(node_id) for node_id in graph)
