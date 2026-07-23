"""AQS data gather — READ-ONLY snapshots from institutional sources."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_research_context() -> dict[str, Any]:
    """Collect advisory copies only — never mutates sources."""
    sources: dict[str, Any] = {
        "irl": None,
        "idw": None,
        "portfolio": None,
        "regime": None,
        "opportunity": None,
        "sic": None,
        "prr": None,
        "audit": None,
    }
    availability: dict[str, bool] = {}

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        sources["irl"] = {
            "dashboard": _safe(irl.dashboard, {}),
            "experiments": _safe(lambda: irl.list_experiments(limit=50), []),
            "leaderboard": _safe(
                lambda: irl.leaderboard(rank_by="composite", limit=10), {}
            ),
            "jobs": _safe(lambda: irl.list_jobs(limit=20), []),
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
        availability["irl"] = False

    wh = _safe(
        lambda: __import__(
            "app.domain.institutional_data_warehouse.store",
            fromlist=["get_warehouse"],
        ).get_warehouse()
    )
    if wh is not None:
        sources["idw"] = {
            "inventory": _safe(wh.inventory, {}),
            "quality": _safe(
                lambda: __import__(
                    "app.domain.institutional_data_warehouse.quality_monitor",
                    fromlist=["run_data_quality_monitor"],
                ).run_data_quality_monitor(wh),
                {},
            ),
            "trades": _safe(lambda: wh.list("trades", limit=500), []),
            "signals": _safe(lambda: wh.list("signals", limit=200), []),
            "research": _safe(lambda: wh.list("research", limit=100), []),
            "regimes": _safe(lambda: wh.list("regimes", limit=100), []),
        }
        availability["idw"] = True
    else:
        availability["idw"] = False

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["analyze_portfolio"],
        ).analyze_portfolio([], starting_equity=10_000.0, include_reports=False),
        {},
    )
    # Prefer richer window when deals available — still read-only
    rich = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90)
    )
    if isinstance(rich, dict) and int(rich.get("trade_count") or 0) > 0:
        sources["portfolio"] = rich
    availability["portfolio"] = isinstance(sources["portfolio"], dict)

    sources["regime"] = _safe(
        lambda: __import__(
            "app.application.services.market_regime_intelligence",
            fromlist=["build_market_regime_intelligence"],
        ).build_market_regime_intelligence(limit=50),
        {},
    )
    availability["regime"] = bool(sources["regime"])

    sources["opportunity"] = _safe(
        lambda: __import__(
            "app.application.services.adaptive_opportunity_timeline",
            fromlist=["timeline_snapshot_from_diagnostics"],
        ).timeline_snapshot_from_diagnostics(
            __import__(
                "app.application.services.strategy_diagnostics",
                fromlist=["get_strategy_diagnostics_store"],
            )
            .get_strategy_diagnostics_store()
            .snapshot(limit=40),
            limit=40,
        ),
        {},
    )
    availability["opportunity"] = bool(sources["opportunity"])

    sources["sic"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_intelligence_center",
            fromlist=["build_strategy_intelligence_center"],
        ).build_strategy_intelligence_center(days=90),
        {},
    )
    availability["sic"] = bool(sources["sic"])

    sources["prr"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_production_readiness_review",
            fromlist=["build_institutional_production_readiness_review"],
        ).build_institutional_production_readiness_review(write_report=False),
        {},
    )
    availability["prr"] = bool(sources["prr"])

    sources["audit"] = _safe(
        lambda: __import__(
            "app.domain.audit_governance.store",
            fromlist=["get_audit_store"],
        ).get_audit_store().list(limit=50),
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
