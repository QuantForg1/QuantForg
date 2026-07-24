"""RES gather — READ-ONLY snapshots from reliability-related sources."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_reliability_sources() -> dict[str, Any]:
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
            "oms": _safe(lambda: wh.list("oms", limit=80), []),
            "gateway": _safe(lambda: wh.list("gateway", limit=80), []),
            "broker": _safe(lambda: wh.list("broker", limit=80), []),
            "diagnostics": _safe(lambda: wh.list("diagnostics", limit=80), []),
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
        sources["idw"] = {}
        availability["idw"] = False

    sources["icc"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_control_center",
            fromlist=["build_institutional_control_center"],
        ).build_institutional_control_center(),
        {},
    )
    availability["icc"] = bool(sources["icc"])

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
        ).get_audit_store().list(limit=60),
        [],
    )
    availability["audit"] = isinstance(sources["audit"], list)

    # EQS cached snapshot only — never force a full EQS rebuild
    sources["eqs"] = _safe(
        lambda: (
            __import__(
                "app.domain.execution_quality_suite", fromlist=["get_eqs"]
            ).get_eqs().store.__dict__.get("_snapshot")
            or {}
        ),
        {},
    )
    availability["eqs"] = bool(sources["eqs"])

    sources["qkg"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["qkg"] = bool(sources["qkg"])

    sources["rc1"] = _safe(
        lambda: __import__(
            "app.application.services.rc1_ops_telemetry",
            fromlist=["Rc1OpsTelemetryService"],
        ).Rc1OpsTelemetryService().collect(),
        {},
    )
    availability["rc1"] = bool(sources["rc1"])

    sources["live_metrics"] = _safe(
        lambda: __import__(
            "app.domain.institutional_trading.reliability.live_metrics",
            fromlist=["LiveMetricsRegistry"],
        ).LiveMetricsRegistry().snapshot(),
        {},
    )
    availability["live_metrics"] = isinstance(sources["live_metrics"], dict)

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
