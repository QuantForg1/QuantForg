"""Dependency map visualization data — health overlay only."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_observability.models import DEPENDENCY_CHAIN


def build_dependency_map(health: dict[str, Any]) -> dict[str, Any]:
    comps = (health.get("components") or {}) if isinstance(health, dict) else {}
    # Map chain nodes to closest component health
    alias = {
        "frontend": "api",
        "api": "api",
        "gateway": "gateway",
        "mt5": "mt5_session",
        "broker": "broker",
        "execution": "execution_queue",
        "warehouse": "warehouse",
        "reports": "operations_center",
    }
    nodes: list[dict[str, Any]] = []
    for name in DEPENDENCY_CHAIN:
        src = alias.get(name, name)
        meta = comps.get(src) or {}
        nodes.append(
            {
                "id": name,
                "component": src,
                "status": meta.get("status") or "unknown",
                "detail": meta.get("detail"),
            }
        )
    edges = [
        {"from": DEPENDENCY_CHAIN[i], "to": DEPENDENCY_CHAIN[i + 1]}
        for i in range(len(DEPENDENCY_CHAIN) - 1)
    ]
    return {
        "status": "available",
        "chain": list(DEPENDENCY_CHAIN),
        "nodes": nodes,
        "edges": edges,
        "observability_only": True,
    }
