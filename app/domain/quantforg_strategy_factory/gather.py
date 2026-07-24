"""QSF gather — READ-ONLY evidence from strategy development subsystems."""

from __future__ import annotations

from typing import Any, Callable

from app.domain.quantforg_strategy_factory.models import INTEGRATIONS


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


def gather_factory_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        sources["irl"] = {
            "experiments": _safe(lambda: irl.list_experiments(limit=20), []),
            "jobs": _safe(lambda: irl.list_jobs(limit=20), []),
        }
        availability["irl"] = True
    else:
        sources["irl"] = {"experiments": [], "jobs": []}
        availability["irl"] = False

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
        return {"simulations": ise.store.list_simulations(limit=25)}

    sources["ise"] = _safe(_ise, {"simulations": []})
    availability["ise"] = isinstance(sources["ise"], dict)

    sims = (
        sources["ise"].get("simulations")
        if isinstance(sources["ise"], dict)
        else []
    )
    replay_sims = [
        s
        for s in (sims if isinstance(sims, list) else [])
        if isinstance(s, dict)
        and (
            "replay" in str(s.get("mode") or "").lower()
            or "historical" in str(s.get("mode") or s.get("scenario") or "").lower()
        )
    ]
    sources["replay"] = {"simulations": replay_sims}
    availability["replay"] = True

    sources["cvf"] = _store_snapshot(
        "app.domain.continuous_validation_framework", "get_cvf"
    )
    availability["cvf"] = bool(sources["cvf"])

    sources["irap"] = _store_snapshot(
        "app.domain.institutional_risk_analytics", "get_irap"
    )
    availability["irap"] = bool(sources["irap"])

    sources["qcs"] = _store_snapshot(
        "app.domain.quantforg_certification_suite", "get_qcs"
    )
    availability["qcs"] = bool(sources["qcs"])

    sources["qdie"] = _store_snapshot(
        "app.domain.quantforg_decision_intelligence", "get_qdie"
    )
    availability["qdie"] = bool(sources["qdie"])

    def _islm() -> dict[str, Any]:
        islm = __import__(
            "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
        ).get_islm()
        return {
            "registry": islm.store.list_strategies(limit=40),
            "approvals": islm.store.list_approvals(limit=20),
        }

    sources["islm"] = _safe(_islm, {"registry": [], "approvals": []})
    availability["islm"] = isinstance(sources["islm"], dict)

    sources["qsmr"] = _store_snapshot(
        "app.domain.quantforg_strategy_marketplace", "get_qsmr"
    )
    availability["qsmr"] = bool(sources["qsmr"])

    sources["qkg"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["qkg"] = bool(sources["qkg"])

    sources["qem"] = _store_snapshot(
        "app.domain.quantforg_event_mesh", "get_qem"
    )
    availability["qem"] = bool(sources["qem"])

    sources["qcdm"] = _store_snapshot(
        "app.domain.quantforg_canonical_data_model", "get_qcdm"
    )
    availability["qcdm"] = bool(sources["qcdm"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "expected_integrations": list(INTEGRATIONS),
        "read_only": True,
        "never_mutates_sources": True,
    }
