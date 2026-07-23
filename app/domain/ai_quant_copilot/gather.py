"""AQC data gather — READ-ONLY snapshots from operational & research sources."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_ops_context() -> dict[str, Any]:
    """Collect advisory copies only — never mutates sources."""
    sources: dict[str, Any] = {
        "icc": None,
        "idw": None,
        "aqs": None,
        "irl": None,
        "diagnostics": None,
        "execution_explain": None,
        "portfolio": None,
        "regime": None,
        "opportunity": None,
        "sic": None,
        "audit": None,
    }
    availability: dict[str, bool] = {}

    sources["icc"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_control_center",
            fromlist=["build_institutional_control_center"],
        ).build_institutional_control_center(),
        {},
    )
    availability["icc"] = bool(sources["icc"])

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
        }
        availability["idw"] = True
    else:
        availability["idw"] = False

    sources["aqs"] = _safe(
        lambda: {
            "recommendations": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_recommendations"],
            )
            .aqs_list_recommendations(limit=100)
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

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        sources["irl"] = {
            "dashboard": _safe(irl.dashboard, {}),
            "experiments": _safe(lambda: irl.list_experiments(limit=30), []),
            "leaderboard": _safe(
                lambda: irl.leaderboard(rank_by="composite", limit=10), {}
            ),
        }
        availability["irl"] = True
    else:
        availability["irl"] = False

    diag = _safe(
        lambda: __import__(
            "app.application.services.strategy_diagnostics",
            fromlist=["get_strategy_diagnostics_store"],
        )
        .get_strategy_diagnostics_store()
        .snapshot(limit=40),
        {},
    )
    sources["diagnostics"] = diag
    availability["diagnostics"] = bool(diag)

    sources["execution_explain"] = _safe(
        lambda: __import__(
            "app.application.services.live_execution_explain",
            fromlist=["explain_snapshot_from_diagnostics"],
        ).explain_snapshot_from_diagnostics(diag or {}),
        {},
    )
    availability["execution_explain"] = bool(sources["execution_explain"])

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90),
        {},
    )
    availability["portfolio"] = isinstance(sources["portfolio"], dict) and bool(
        sources["portfolio"]
    )

    sources["regime"] = _safe(
        lambda: __import__(
            "app.application.services.market_regime_intelligence",
            fromlist=["build_market_regime_intelligence"],
        ).build_market_regime_intelligence(limit=40),
        {},
    )
    availability["regime"] = bool(sources["regime"])

    sources["opportunity"] = _safe(
        lambda: __import__(
            "app.application.services.adaptive_opportunity_timeline",
            fromlist=["timeline_snapshot_from_diagnostics"],
        ).timeline_snapshot_from_diagnostics(diag or {}, limit=40),
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

    sources["audit"] = _safe(
        lambda: __import__(
            "app.domain.audit_governance.store",
            fromlist=["get_audit_store"],
        ).get_audit_store().list(limit=60),
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
