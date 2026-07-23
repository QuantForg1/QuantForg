"""QKG gather — READ-ONLY snapshots from institutional sources."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_knowledge_sources() -> dict[str, Any]:
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
            "trades": _safe(lambda: wh.list("trades", limit=80), []),
            "signals": _safe(lambda: wh.list("signals", limit=80), []),
            "regimes": _safe(lambda: wh.list("regimes", limit=40), []),
            "research": _safe(lambda: wh.list("research", limit=40), []),
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
        }
        availability["irl"] = True
    else:
        sources["irl"] = {}
        availability["irl"] = False

    sources["aqs"] = _safe(
        lambda: {
            "recommendations": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_recommendations"],
            )
            .aqs_list_recommendations(limit=60)
            .get("recommendations")
            or [],
            "reports": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_reports"],
            )
            .aqs_list_reports(limit=15)
            .get("reports")
            or [],
        },
        {"recommendations": [], "reports": []},
    )
    availability["aqs"] = isinstance(sources["aqs"], dict)

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
        ).build_market_regime_intelligence(limit=30),
        {},
    )
    availability["regime"] = bool(sources["regime"])

    sources["diagnostics"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_diagnostics",
            fromlist=["get_strategy_diagnostics_store"],
        )
        .get_strategy_diagnostics_store()
        .snapshot(limit=30),
        {},
    )
    availability["diagnostics"] = bool(sources["diagnostics"])

    sources["icc"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_control_center",
            fromlist=["build_institutional_control_center"],
        ).build_institutional_control_center(),
        {},
    )
    availability["icc"] = bool(sources["icc"])

    sources["sic"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_intelligence_center",
            fromlist=["build_strategy_intelligence_center"],
        ).build_strategy_intelligence_center(days=90),
        {},
    )
    availability["sic"] = bool(sources["sic"])

    sources["audit"] = _safe(
        lambda: __import__(
            "app.domain.audit_governance.store",
            fromlist=["get_audit_store"],
        ).get_audit_store().list(limit=40),
        [],
    )
    availability["audit"] = isinstance(sources["audit"], list)

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
