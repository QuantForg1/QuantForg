"""QPM gather — READ-ONLY evidence for portfolio orchestration."""

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


def gather_portfolio_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    def _qsmr() -> dict[str, Any]:
        qsmr = __import__(
            "app.domain.quantforg_strategy_marketplace", fromlist=["get_qsmr"]
        ).get_qsmr()
        return {
            "registry": qsmr.store.list_strategies(limit=50),
            "snapshot": qsmr.store.get_snapshot()
            if hasattr(qsmr.store, "get_snapshot")
            else {},
        }

    sources["qsmr"] = _safe(_qsmr, {"registry": [], "snapshot": {}})
    availability["qsmr"] = isinstance(sources["qsmr"], dict)

    sources["irap"] = _store_snapshot(
        "app.domain.institutional_risk_analytics", "get_irap"
    )
    availability["irap"] = bool(sources["irap"])

    sources["cvf"] = _store_snapshot(
        "app.domain.continuous_validation_framework", "get_cvf"
    )
    availability["cvf"] = bool(sources["cvf"])

    def _ise() -> dict[str, Any]:
        ise = __import__(
            "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
        ).get_ise()
        return {"simulations": ise.store.list_simulations(limit=20)}

    sources["ise"] = _safe(_ise, {"simulations": []})
    availability["ise"] = isinstance(sources["ise"], dict)

    def _iep() -> dict[str, Any]:
        iep = __import__(
            "app.domain.institutional_experimentation_platform", fromlist=["get_iep"]
        ).get_iep()
        return {"registry": iep.store.list_experiments(limit=20)}

    sources["iep"] = _safe(_iep, {"registry": []})
    availability["iep"] = isinstance(sources["iep"], dict)

    def _islm() -> dict[str, Any]:
        islm = __import__(
            "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
        ).get_islm()
        return {"registry": islm.store.list_strategies(limit=30)}

    sources["islm"] = _safe(_islm, {"registry": []})
    availability["islm"] = isinstance(sources["islm"], dict)

    sources["eqs"] = _store_snapshot(
        "app.domain.execution_quality_suite", "get_eqs"
    )
    availability["eqs"] = bool(sources["eqs"])

    sources["res"] = _store_snapshot(
        "app.domain.reliability_engineering_suite", "get_res"
    )
    availability["res"] = bool(sources["res"])

    sources["qcs"] = _store_snapshot(
        "app.domain.quantforg_certification_suite", "get_qcs"
    )
    availability["qcs"] = bool(sources["qcs"])

    sources["icp"] = _store_snapshot(
        "app.domain.institutional_control_plane", "get_icp"
    )
    availability["icp"] = bool(sources["icp"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
