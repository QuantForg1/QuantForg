"""QCS gather — READ-ONLY evidence from all major enterprise subsystems."""

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


def gather_certification_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        experiments = _safe(lambda: irl.list_experiments(limit=30), [])
        jobs = _safe(lambda: irl.list_jobs(limit=30), [])
        leaderboard = _safe(
            lambda: irl.leaderboard(rank_by="composite", limit=15), {}
        )
        sources["irl"] = {
            "experiments": experiments,
            "leaderboard": leaderboard,
            "jobs": jobs,
        }
        replay_jobs = []
        for j in jobs if isinstance(jobs, list) else []:
            if not isinstance(j, dict):
                continue
            blob = f"{j.get('kind') or ''} {j.get('type') or ''} {j.get('name') or ''}".lower()
            if "replay" in blob:
                replay_jobs.append(j)
        sources["replay"] = {"jobs": replay_jobs, "from_irl": True}
        sources["benchmark"] = {"leaderboard": leaderboard, "from_irl": True}
        availability["irl"] = True
        availability["replay"] = True
        availability["benchmark"] = True
    else:
        sources["irl"] = {}
        sources["replay"] = {}
        sources["benchmark"] = {}
        availability["irl"] = False
        availability["replay"] = False
        availability["benchmark"] = False

    def _ise() -> dict[str, Any]:
        ise = __import__(
            "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
        ).get_ise()
        return {
            "simulations": ise.store.list_simulations(limit=20),
            "reports": ise.store.list_reports(limit=10)
            if hasattr(ise.store, "list_reports")
            else [],
        }

    sources["ise"] = _safe(_ise, {"simulations": [], "reports": []})
    availability["ise"] = isinstance(sources["ise"], dict)

    # Enrich replay from ISE historical modes
    sims = sources["ise"].get("simulations") if isinstance(sources["ise"], dict) else []
    if isinstance(sims, list):
        replay_sims = [
            s
            for s in sims
            if isinstance(s, dict)
            and (
                "replay" in str(s.get("mode") or "").lower()
                or "historical" in str(s.get("mode") or s.get("scenario") or "").lower()
            )
        ]
        if replay_sims:
            sources["replay"] = {
                **(sources.get("replay") or {}),
                "simulations": replay_sims,
            }
            availability["replay"] = True

    sources["cvf"] = _store_snapshot(
        "app.domain.continuous_validation_framework", "get_cvf"
    )
    availability["cvf"] = bool(sources["cvf"])

    def _iep() -> dict[str, Any]:
        iep = __import__(
            "app.domain.institutional_experimentation_platform", fromlist=["get_iep"]
        ).get_iep()
        return {
            "registry": iep.store.list_experiments(limit=20),
            "snapshot": iep.store.get_snapshot()
            if hasattr(iep.store, "get_snapshot")
            else {},
        }

    sources["iep"] = _safe(_iep, {"registry": [], "snapshot": {}})
    availability["iep"] = isinstance(sources["iep"], dict)

    def _islm() -> dict[str, Any]:
        islm = __import__(
            "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
        ).get_islm()
        return {
            "registry": islm.store.list_strategies(limit=20),
            "approvals": islm.store.list_approvals(limit=15),
        }

    sources["islm"] = _safe(_islm, {"registry": [], "approvals": []})
    availability["islm"] = isinstance(sources["islm"], dict)

    sources["irap"] = _store_snapshot(
        "app.domain.institutional_risk_analytics", "get_irap"
    )
    availability["irap"] = bool(sources["irap"])

    sources["eqs"] = _store_snapshot(
        "app.domain.execution_quality_suite", "get_eqs"
    )
    availability["eqs"] = bool(sources["eqs"])

    sources["res"] = _store_snapshot(
        "app.domain.reliability_engineering_suite", "get_res"
    )
    availability["res"] = bool(sources["res"])

    def _irdp() -> dict[str, Any]:
        irdp = __import__(
            "app.domain.institutional_release_deployment", fromlist=["get_irdp"]
        ).get_irdp()
        return {
            "releases": irdp.store.list_releases(limit=15),
            "approvals": irdp.store.list_approvals(limit=15),
            "reports": irdp.store.list_reports(limit=10)
            if hasattr(irdp.store, "list_reports")
            else [],
        }

    sources["irdp"] = _safe(_irdp, {"releases": [], "approvals": [], "reports": []})
    availability["irdp"] = isinstance(sources["irdp"], dict)

    sources["icp"] = _store_snapshot(
        "app.domain.institutional_control_plane", "get_icp"
    )
    availability["icp"] = bool(sources["icp"])

    sources["idw"] = _safe(
        lambda: {
            "analytics": __import__(
                "app.application.services.institutional_data_warehouse",
                fromlist=["query_analytics"],
            ).query_analytics(),
            "quality": __import__(
                "app.application.services.institutional_data_warehouse",
                fromlist=["query_data_quality"],
            ).query_data_quality(),
        },
        {},
    )
    availability["idw"] = bool(sources["idw"])

    sources["aqs"] = _safe(
        lambda: {
            "recommendations": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_recommendations"],
            )
            .aqs_list_recommendations(limit=25)
            .get("recommendations")
            or [],
        },
        {"recommendations": []},
    )
    availability["aqs"] = isinstance(sources["aqs"], dict)

    sources["aqc"] = {"snapshot": _store_snapshot("app.domain.ai_quant_copilot", "get_aqc")}
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
