"""Quant Studio — visual strategy block catalog and graph compilation."""

from __future__ import annotations

from typing import Any

BLOCK_CATALOG: list[dict[str, Any]] = [
    {
        "id": "condition",
        "category": "Conditions",
        "label": "Condition",
        "ports": ["out"],
        "params": ["op", "left", "right"],
    },
    {
        "id": "indicator",
        "category": "Indicators",
        "label": "Indicator",
        "ports": ["out"],
        "params": ["name", "period"],
    },
    {
        "id": "price",
        "category": "Price",
        "label": "Price",
        "ports": ["out"],
        "params": ["field"],
    },
    {
        "id": "risk",
        "category": "Risk",
        "label": "Risk",
        "ports": ["in", "out"],
        "params": ["max_risk_pct", "lot_size"],
    },
    {
        "id": "time",
        "category": "Time",
        "label": "Time Filter",
        "ports": ["out"],
        "params": ["start_hour", "end_hour"],
    },
    {
        "id": "volume",
        "category": "Volume",
        "label": "Volume",
        "ports": ["out"],
        "params": ["min_volume"],
    },
    {
        "id": "news",
        "category": "News",
        "label": "News Filter",
        "ports": ["out"],
        "params": ["max_impact"],
    },
    {
        "id": "session",
        "category": "Sessions",
        "label": "Session",
        "ports": ["out"],
        "params": ["session"],
    },
    {
        "id": "correlation",
        "category": "Correlation",
        "label": "Correlation Cap",
        "ports": ["out"],
        "params": ["max_corr"],
    },
    {
        "id": "ai",
        "category": "AI",
        "label": "AI Gate",
        "ports": ["in", "out"],
        "params": ["min_confidence"],
    },
    {
        "id": "execution",
        "category": "Execution",
        "label": "Execution Intent",
        "ports": ["in"],
        "params": ["side"],
    },
    {
        "id": "exit",
        "category": "Exit",
        "label": "Exit Rules",
        "ports": ["in"],
        "params": ["sl_distance", "tp_distance"],
    },
]


def compile_strategy_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Compile a visual block graph into assumptions / notes — no code required."""
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    if not nodes:
        return {
            "status": "unavailable",
            "reason": "Strategy graph has no blocks",
            "assumptions": {},
            "blocks_used": [],
            "advisory_only": True,
            "autonomous_trading": False,
        }

    blocks_used = [str(n.get("type") or n.get("id") or "") for n in nodes]
    assumptions: dict[str, Any] = {
        "lot_size": "0.10",
        "stop_loss_distance": "0.0020",
        "take_profit_distance": "0.0040",
    }
    warnings: list[str] = []
    has_exit = False
    has_exec = False
    for n in nodes:
        t = str(n.get("type") or "")
        params = dict(n.get("params") or {})
        if t == "exit":
            has_exit = True
            if params.get("sl_distance"):
                assumptions["stop_loss_distance"] = str(params["sl_distance"])
            if params.get("tp_distance"):
                assumptions["take_profit_distance"] = str(params["tp_distance"])
        if t == "risk" and params.get("lot_size"):
            assumptions["lot_size"] = str(params["lot_size"])
        if t == "execution":
            has_exec = True
        if t == "session" and params.get("session"):
            assumptions["preferred_session"] = str(params["session"])

    if not has_exit:
        warnings.append(
            "No Exit block — default SL/TP distances applied for simulation"
        )
    if not has_exec:
        warnings.append("No Execution block — simulation uses auto_analysis entries")
    if len(edges) == 0 and len(nodes) > 1:
        warnings.append("Blocks are not connected — treat as loose parameter bag")

    return {
        "status": "available",
        "blocks_used": blocks_used,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "assumptions": assumptions,
        "warnings": warnings,
        "why": {
            "summary": f"Compiled {len(nodes)} blocks into simulation assumptions",
            "supporting_factors": warnings or ["Graph compiled cleanly"],
        },
        "advisory_only": True,
        "autonomous_trading": False,
        "never_submits_orders": True,
    }
