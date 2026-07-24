"""IRAP gather — READ-ONLY snapshots from risk-related sources."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_risk_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90),
        {},
    )
    availability["portfolio"] = bool(sources["portfolio"])

    wh = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.store",
            fromlist=["get_warehouse"],
        ).get_warehouse()
    )
    if wh is not None:
        sources["idw"] = {
            "trades": _safe(lambda: wh.list("trades", limit=200), []),
            "signals": _safe(lambda: wh.list("signals", limit=80), []),
            "regimes": _safe(lambda: wh.list("regimes", limit=40), []),
        }
        availability["idw"] = True
    else:
        sources["idw"] = {}
        availability["idw"] = False

    # Cached snapshots only — avoid forcing full rebuilds
    sources["ise"] = _safe(
        lambda: {
            "simulations": __import__(
                "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
            )
            .get_ise()
            .store.list_simulations(limit=20),
        },
        {"simulations": []},
    )
    availability["ise"] = isinstance(sources["ise"], dict)

    sources["cvf"] = _safe(
        lambda: __import__(
            "app.domain.continuous_validation_framework", fromlist=["get_cvf"]
        ).get_cvf().store.__dict__.get("_snapshot")
        or {},
        {},
    )
    availability["cvf"] = bool(sources["cvf"])

    sources["eqs"] = _safe(
        lambda: __import__(
            "app.domain.execution_quality_suite", fromlist=["get_eqs"]
        ).get_eqs().store.__dict__.get("_snapshot")
        or {},
        {},
    )
    availability["eqs"] = bool(sources["eqs"])

    sources["res"] = _safe(
        lambda: __import__(
            "app.domain.reliability_engineering_suite", fromlist=["get_res"]
        ).get_res().store.__dict__.get("_snapshot")
        or {},
        {},
    )
    availability["res"] = bool(sources["res"])

    sources["qkg"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["qkg"] = bool(sources["qkg"])

    sources["sic"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_intelligence_center",
            fromlist=["build_strategy_intelligence_center"],
        ).build_strategy_intelligence_center(days=90),
        {},
    )
    availability["sic"] = bool(sources["sic"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
