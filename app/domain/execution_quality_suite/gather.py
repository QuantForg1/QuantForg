"""EQS gather — READ-ONLY snapshots from execution & institutional sources."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_execution_sources() -> dict[str, Any]:
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
            "oms": _safe(lambda: wh.list("oms", limit=100), []),
            "gateway": _safe(lambda: wh.list("gateway", limit=100), []),
            "broker": _safe(lambda: wh.list("broker", limit=100), []),
            "execution": _safe(lambda: wh.list("execution", limit=100), []),
            "trades": _safe(lambda: wh.list("trades", limit=100), []),
            "inventory": _safe(wh.inventory, {}),
        }
        availability["idw"] = True
    else:
        sources["idw"] = {}
        availability["idw"] = False

    sources["journal"] = _safe(
        lambda: __import__(
            "app.presentation.dependencies.execution",
            fromlist=["get_execution_journal"],
        ).get_execution_journal().all_recent(limit=150),
        [],
    )
    availability["journal"] = isinstance(sources["journal"], list)

    sources["icc"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_control_center",
            fromlist=["build_institutional_control_center"],
        ).build_institutional_control_center(),
        {},
    )
    availability["icc"] = bool(sources["icc"])

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90),
        {},
    )
    availability["portfolio"] = bool(sources["portfolio"])

    sources["diagnostics"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_diagnostics",
            fromlist=["get_strategy_diagnostics_store"],
        )
        .get_strategy_diagnostics_store()
        .snapshot(limit=40),
        {},
    )
    availability["diagnostics"] = bool(sources["diagnostics"])

    sources["audit"] = _safe(
        lambda: __import__(
            "app.domain.audit_governance.store",
            fromlist=["get_audit_store"],
        ).get_audit_store().list(limit=50),
        [],
    )
    availability["audit"] = isinstance(sources["audit"], list)

    sources["qkg"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["qkg"] = bool(sources["qkg"])

    sources["live_metrics"] = _safe(
        lambda: __import__(
            "app.domain.institutional_trading.reliability.live_metrics",
            fromlist=["LiveMetricsRegistry"],
        ).LiveMetricsRegistry().snapshot(),
        {},
    )
    availability["live_metrics"] = isinstance(sources["live_metrics"], dict)

    sources["rc1"] = _safe(
        lambda: __import__(
            "app.application.services.rc1_ops_telemetry",
            fromlist=["Rc1OpsTelemetryService"],
        ).Rc1OpsTelemetryService().collect(),
        {},
    )
    availability["rc1"] = bool(sources["rc1"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
