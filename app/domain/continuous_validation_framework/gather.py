"""CVF gather — READ-ONLY snapshots from research & production analytics."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_validation_sources() -> dict[str, Any]:
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
            "trades": _safe(lambda: wh.list("trades", limit=120), []),
            "signals": _safe(lambda: wh.list("signals", limit=80), []),
            "research": _safe(lambda: wh.list("research", limit=40), []),
            "regimes": _safe(lambda: wh.list("regimes", limit=40), []),
            "inventory": _safe(wh.inventory, {}),
        }
        availability["idw"] = True
    else:
        sources["idw"] = {}
        availability["idw"] = False

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        sources["irl"] = {
            "experiments": _safe(lambda: irl.list_experiments(limit=40), []),
            "jobs": _safe(lambda: irl.list_jobs(limit=30), []),
            "leaderboard": _safe(
                lambda: irl.leaderboard(rank_by="composite", limit=10), {}
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

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90),
        {},
    )
    availability["portfolio"] = bool(sources["portfolio"])

    sources["regime"] = _safe(
        lambda: __import__(
            "app.application.services.market_regime_intelligence",
            fromlist=["build_market_regime_intelligence"],
        ).build_market_regime_intelligence(limit=40),
        {},
    )
    availability["regime"] = bool(sources["regime"])

    sources["sic"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_intelligence_center",
            fromlist=["build_strategy_intelligence_center"],
        ).build_strategy_intelligence_center(days=90),
        {},
    )
    availability["sic"] = bool(sources["sic"])

    sources["aqs"] = _safe(
        lambda: {
            "recommendations": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_recommendations"],
            )
            .aqs_list_recommendations(limit=40)
            .get("recommendations")
            or [],
            "reports": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_reports"],
            )
            .aqs_list_reports(limit=10)
            .get("reports")
            or [],
        },
        {"recommendations": [], "reports": []},
    )
    availability["aqs"] = isinstance(sources["aqs"], dict)

    sources["aqc"] = _safe(
        lambda: {
            "conversations": __import__(
                "app.application.services.ai_quant_copilot",
                fromlist=["aqc_list_conversations"],
            )
            .aqc_list_conversations(limit=10)
            .get("conversations")
            or [],
        },
        {"conversations": []},
    )
    availability["aqc"] = isinstance(sources["aqc"], dict)

    # Cached snapshots only — avoid forcing full EQS/RES rebuilds
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

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
