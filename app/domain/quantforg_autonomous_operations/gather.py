"""AOC gather — READ-ONLY aggregation across enterprise subsystems."""

from __future__ import annotations

from typing import Any, Callable


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def _store_snapshot(import_path: str, getter: str) -> dict[str, Any]:
    def _load() -> dict[str, Any]:
        mod = __import__(import_path, fromlist=[getter])
        plat = getattr(mod, getter)()
        store = plat.store
        if hasattr(store, "get_snapshot"):
            snap = store.get_snapshot()
            return snap if isinstance(snap, dict) else {}
        snap = getattr(store, "_snapshot", None)
        return dict(snap) if isinstance(snap, dict) else {}

    out = _safe(_load, {})
    return out if isinstance(out, dict) else {}


def gather_operations_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    sources["icp"] = _store_snapshot(
        "app.domain.institutional_control_plane", "get_icp"
    )
    availability["icp"] = bool(sources["icp"])

    sources["qcs"] = _store_snapshot(
        "app.domain.quantforg_certification_suite", "get_qcs"
    )
    availability["qcs"] = bool(sources["qcs"])

    sources["qpm"] = _store_snapshot(
        "app.domain.quantforg_portfolio_manager", "get_qpm"
    )
    availability["qpm"] = bool(sources["qpm"])

    sources["irap"] = _store_snapshot(
        "app.domain.institutional_risk_analytics", "get_irap"
    )
    availability["irap"] = bool(sources["irap"])

    def _islm() -> dict[str, Any]:
        islm = __import__(
            "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
        ).get_islm()
        return {
            "registry": islm.store.list_strategies(limit=30),
            "approvals": islm.store.list_approvals(limit=15),
        }

    sources["islm"] = _safe(_islm, {"registry": [], "approvals": []})
    availability["islm"] = isinstance(sources["islm"], dict)

    def _iep() -> dict[str, Any]:
        iep = __import__(
            "app.domain.institutional_experimentation_platform", fromlist=["get_iep"]
        ).get_iep()
        return {
            "registry": iep.store.list_experiments(limit=25),
            "snapshot": iep.store.get_snapshot()
            if hasattr(iep.store, "get_snapshot")
            else {},
        }

    sources["iep"] = _safe(_iep, {"registry": [], "snapshot": {}})
    availability["iep"] = isinstance(sources["iep"], dict)

    def _ise() -> dict[str, Any]:
        ise = __import__(
            "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
        ).get_ise()
        return {"simulations": ise.store.list_simulations(limit=20)}

    sources["ise"] = _safe(_ise, {"simulations": []})
    availability["ise"] = isinstance(sources["ise"], dict)

    sources["cvf"] = _store_snapshot(
        "app.domain.continuous_validation_framework", "get_cvf"
    )
    availability["cvf"] = bool(sources["cvf"])

    sources["eqs"] = _store_snapshot(
        "app.domain.execution_quality_suite", "get_eqs"
    )
    availability["eqs"] = bool(sources["eqs"])

    sources["res"] = _store_snapshot(
        "app.domain.reliability_engineering_suite", "get_res"
    )
    availability["res"] = bool(sources["res"])

    sources["aqs"] = _safe(
        lambda: {
            "recommendations": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_recommendations"],
            )
            .aqs_list_recommendations(limit=30)
            .get("recommendations")
            or [],
        },
        {"recommendations": []},
    )
    availability["aqs"] = isinstance(sources["aqs"], dict)

    sources["aqc"] = {
        "snapshot": _store_snapshot("app.domain.ai_quant_copilot", "get_aqc")
    }
    availability["aqc"] = True

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
