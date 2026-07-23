"""Quant Knowledge Graph (QKG) — knowledge layer of QuantForg Enterprise V2.

Completely read-only. Connects institutional subsystems as nodes and
relationships. Never modifies production, research, risk, strategy,
gateway, OMS, scheduler, or thresholds.
"""

from __future__ import annotations

from app.domain.quant_knowledge_graph.platform import QuantKnowledgeGraph

__all__ = ["QuantKnowledgeGraph", "get_qkg", "qkg_query_for_ai"]

_QKG: QuantKnowledgeGraph | None = None


def get_qkg() -> QuantKnowledgeGraph:
    global _QKG
    if _QKG is None:
        _QKG = QuantKnowledgeGraph()
    return _QKG


def qkg_query_for_ai(question: str, *, node_id: str | None = None) -> dict:
    """Allow AQS and AQC to query the graph (read-only)."""
    return get_qkg().query_for_ai(question, node_id=node_id)
