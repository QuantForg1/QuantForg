"""Application facade — Quant Knowledge Graph (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quant_knowledge_graph import get_qkg
from app.domain.quant_knowledge_graph.models import ISOLATION_FLAGS


def build_qkg_dashboard() -> dict[str, Any]:
    payload = get_qkg().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "never_modifies_production": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def qkg_search(*, q: str | None = None, node_type: str | None = None, limit: int = 50) -> dict[str, Any]:
    return get_qkg().search(q=q, node_type=node_type, limit=limit)


def qkg_relationships(node_id: str) -> dict[str, Any]:
    return get_qkg().relationships(node_id)


def qkg_dependencies(node_id: str, *, depth: int = 3) -> dict[str, Any]:
    return get_qkg().dependencies(node_id, depth=depth)


def qkg_evidence(node_id: str) -> dict[str, Any]:
    return get_qkg().evidence(node_id)


def qkg_recommendation_trace(recommendation_id: str) -> dict[str, Any]:
    return get_qkg().recommendation_trace(recommendation_id)


def qkg_lineage(node_id: str) -> dict[str, Any]:
    return get_qkg().lineage(node_id)


def qkg_impact(node_id: str) -> dict[str, Any]:
    return get_qkg().impact(node_id)


def qkg_root_cause(node_id: str) -> dict[str, Any]:
    return get_qkg().root_cause(node_id)


def qkg_ai(question: str, *, node_id: str | None = None) -> dict[str, Any]:
    return get_qkg().query_for_ai(question, node_id=node_id)
