"""ISE gather — READ-ONLY historical baselines for digital twin."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_simulation_context() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    wh = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.store",
            fromlist=["get_warehouse"],
        ).get_warehouse()
    )
    if wh is not None:
        sources["idw"] = {
            "trades": _safe(lambda: wh.list("trades", limit=200), []),
            "signals": _safe(lambda: wh.list("signals", limit=100), []),
            "regimes": _safe(lambda: wh.list("regimes", limit=40), []),
        }
        availability["idw"] = True
    else:
        sources["idw"] = {}
        availability["idw"] = False

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90),
        {},
    )
    availability["portfolio"] = bool(sources["portfolio"])

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        sources["irl"] = {
            "leaderboard": _safe(
                lambda: irl.leaderboard(rank_by="composite", limit=5), {}
            ),
            "benchmark": _safe(
                lambda: __import__(
                    "app.application.services.institutional_research_lab",
                    fromlist=["irl_benchmark_view"],
                ).irl_benchmark_view(),
                {},
            ),
        }
        availability["irl"] = True
    else:
        sources["irl"] = {}
        availability["irl"] = False

    sources["regime"] = _safe(
        lambda: __import__(
            "app.application.services.market_regime_intelligence",
            fromlist=["build_market_regime_intelligence"],
        ).build_market_regime_intelligence(limit=20),
        {},
    )
    availability["regime"] = bool(sources["regime"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
        "digital_twin": True,
    }
