"""QEM gather — READ-ONLY evidence used to derive mesh events."""

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


def gather_event_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    sources["trading_engine"] = _safe(
        lambda: {
            "icc": __import__(
                "app.application.services.institutional_control_center",
                fromlist=["build_institutional_control_center"],
            ).build_institutional_control_center(),
        },
        {},
    )
    availability["trading_engine"] = bool(sources["trading_engine"])

    icc: dict[str, Any] = {}
    te = sources.get("trading_engine")
    if isinstance(te, dict) and isinstance(te.get("icc"), dict):
        icc = te["icc"]
    sections = icc.get("sections") if isinstance(icc.get("sections"), dict) else {}
    sources["oms"] = {"live_trading": sections.get("live_trading"), "from": "icc"}
    sources["gateway"] = {"system_status": sections.get("system_status"), "from": "icc"}
    availability["oms"] = True
    availability["gateway"] = True

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        jobs = _safe(lambda: irl.list_jobs(limit=20), [])
        sources["research_lab"] = {
            "experiments": _safe(lambda: irl.list_experiments(limit=20), []),
            "jobs": jobs,
        }
        availability["research_lab"] = True
    else:
        sources["research_lab"] = {"experiments": [], "jobs": []}
        jobs = []
        availability["research_lab"] = False

    def _ise() -> dict[str, Any]:
        ise = __import__(
            "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
        ).get_ise()
        return {"simulations": ise.store.list_simulations(limit=25)}

    sources["simulation"] = _safe(_ise, {"simulations": []})
    availability["simulation"] = isinstance(sources["simulation"], dict)

    sims = (
        sources["simulation"].get("simulations")
        if isinstance(sources["simulation"], dict)
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
    replay_jobs = [
        j
        for j in (jobs if isinstance(jobs, list) else [])
        if isinstance(j, dict)
        and "replay" in f"{j.get('kind') or ''} {j.get('type') or ''}".lower()
    ]
    sources["replay"] = {"simulations": replay_sims, "jobs": replay_jobs}
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

    sources["qpm"] = _store_snapshot(
        "app.domain.quantforg_portfolio_manager", "get_qpm"
    )
    availability["qpm"] = bool(sources["qpm"])

    def _islm() -> dict[str, Any]:
        islm = __import__(
            "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
        ).get_islm()
        return {
            "registry": islm.store.list_strategies(limit=30),
            "approvals": islm.store.list_approvals(limit=20),
        }

    sources["islm"] = _safe(_islm, {"registry": [], "approvals": []})
    availability["islm"] = isinstance(sources["islm"], dict)

    def _irdp() -> dict[str, Any]:
        irdp = __import__(
            "app.domain.institutional_release_deployment", fromlist=["get_irdp"]
        ).get_irdp()
        rollbacks = (
            irdp.store.list_rollbacks(limit=10)
            if hasattr(irdp.store, "list_rollbacks")
            else []
        )
        return {
            "releases": irdp.store.list_releases(limit=20),
            "approvals": irdp.store.list_approvals(limit=20),
            "rollbacks": rollbacks,
        }

    sources["irdp"] = _safe(
        _irdp, {"releases": [], "approvals": [], "rollbacks": []}
    )
    availability["irdp"] = isinstance(sources["irdp"], dict)

    sources["aoc"] = _store_snapshot(
        "app.domain.quantforg_autonomous_operations", "get_aoc"
    )
    availability["aoc"] = bool(sources["aoc"])

    sources["icp"] = _store_snapshot(
        "app.domain.institutional_control_plane", "get_icp"
    )
    availability["icp"] = bool(sources["icp"])

    # EQS / RES feed execution & reliability alerts (not listed as mesh sources,
    # but enrich alert categories used by gateway/OMS consumers).
    sources["eqs"] = _store_snapshot(
        "app.domain.execution_quality_suite", "get_eqs"
    )
    sources["res"] = _store_snapshot(
        "app.domain.reliability_engineering_suite", "get_res"
    )

    sources["knowledge_graph"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["knowledge_graph"] = bool(sources["knowledge_graph"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
