"""Quant Knowledge Graph API — read-only knowledge layer.

Prefix: /qkg
Never modifies production, research, risk, strategy, gateway, OMS,
scheduler, or thresholds.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qkg", tags=["quant-knowledge-graph"])


class AiQueryBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    node_id: str | None = Field(default=None, max_length=200)


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "never_modifies_production": True,
        "knowledge_layer_read_only": True,
    }


@router.get("/dashboard")
def qkg_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import build_qkg_dashboard

    payload = build_qkg_dashboard()
    payload.update(_flags())
    return payload


@router.get("/search")
def qkg_search(
    _user: CurrentUser,
    q: str | None = None,
    node_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_search as _search

    payload = _search(q=q, node_type=node_type, limit=limit)
    payload.update(_flags())
    return payload


@router.get("/relationships/{node_id:path}")
def qkg_relationships(node_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_relationships as _rel

    payload = _rel(node_id)
    payload.update(_flags())
    return payload


@router.get("/dependencies/{node_id:path}")
def qkg_dependencies(
    node_id: str,
    _user: CurrentUser,
    depth: int = Query(default=3, ge=1, le=8),
) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_dependencies as _dep

    payload = _dep(node_id, depth=depth)
    payload.update(_flags())
    return payload


@router.get("/evidence/{node_id:path}")
def qkg_evidence(node_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_evidence as _ev

    payload = _ev(node_id)
    payload.update(_flags())
    return payload


@router.get("/recommendation-trace/{recommendation_id:path}")
def qkg_rec_trace(recommendation_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import (
        qkg_recommendation_trace,
    )

    payload = qkg_recommendation_trace(recommendation_id)
    payload.update(_flags())
    return payload


@router.get("/lineage/{node_id:path}")
def qkg_lineage(node_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_lineage as _lin

    payload = _lin(node_id)
    payload.update(_flags())
    return payload


@router.get("/impact/{node_id:path}")
def qkg_impact(node_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_impact as _imp

    payload = _imp(node_id)
    payload.update(_flags())
    return payload


@router.get("/root-cause/{node_id:path}")
def qkg_root_cause(node_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_root_cause as _rc

    payload = _rc(node_id)
    payload.update(_flags())
    return payload


@router.get("/ai")
def qkg_ai_get(
    _user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=500),
    node_id: str | None = None,
) -> dict[str, Any]:
    from app.application.services.quant_knowledge_graph import qkg_ai

    payload = qkg_ai(q, node_id=node_id)
    payload.update(_flags())
    return payload


@router.post("/ai")
def qkg_ai_post(body: AiQueryBody, _user: CurrentUser) -> dict[str, Any]:
    """Read-only AI graph query for AQS/AQC consumers."""
    from app.application.services.quant_knowledge_graph import qkg_ai

    payload = qkg_ai(body.question, node_id=body.node_id)
    payload.update(_flags())
    return payload


@router.get("/graph")
def qkg_graph(
    _user: CurrentUser,
    limit_nodes: int = Query(default=200, ge=1, le=1000),
    limit_edges: int = Query(default=400, ge=1, le=2000),
) -> dict[str, Any]:
    from app.domain.quant_knowledge_graph import get_qkg

    g = get_qkg().graph()
    return {
        "nodes": (g.get("nodes") or [])[:limit_nodes],
        "edges": (g.get("edges") or [])[:limit_edges],
        "stats": g.get("stats"),
        **_flags(),
    }
