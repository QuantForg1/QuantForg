"""Decision Graph — DAG of orchestration stages (advisory)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STAGE_ORDER: tuple[str, ...] = (
    "idle",
    "evaluating",
    "alpha",
    "policy",
    "rules",
    "plugins",
    "risk",
    "safety",
    "decision",
    "terminal",
)


@dataclass(frozen=True, slots=True)
class GraphNode:
    stage: str
    ok: bool | None
    detail: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "detail": self.detail,
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
        }


@dataclass
class DecisionGraph:
    nodes: list[GraphNode]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": list(STAGE_ORDER),
            "nodes": [n.to_dict() for n in self.nodes],
            "bypasses_risk": False,
            "bypasses_safety": False,
            "never_order_send": True,
        }

    @staticmethod
    def build(stage_results: list[dict[str, Any]]) -> DecisionGraph:
        nodes: list[GraphNode] = []
        for row in stage_results:
            nodes.append(
                GraphNode(
                    stage=str(row.get("stage") or "unknown"),
                    ok=row.get("ok") if isinstance(row.get("ok"), bool) else None,
                    detail=str(row.get("detail") or ""),
                    inputs=dict(row.get("inputs") or {}),
                    outputs=dict(row.get("outputs") or {}),
                )
            )
        return DecisionGraph(nodes=nodes)
