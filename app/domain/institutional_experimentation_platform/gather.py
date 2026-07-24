"""IEP gather — READ-ONLY evidence from research, validation, risk, AI."""

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


def gather_experiment_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    irl = _safe(
        lambda: __import__(
            "app.domain.institutional_research_lab", fromlist=["get_irl"]
        ).get_irl()
    )
    if irl is not None:
        sources["irl"] = {
            "experiments": _safe(lambda: irl.list_experiments(limit=50), []),
            "leaderboard": _safe(
                lambda: irl.leaderboard(rank_by="composite", limit=20), {}
            ),
            "jobs": _safe(lambda: irl.list_jobs(limit=30), []),
        }
        availability["irl"] = True
    else:
        sources["irl"] = {"experiments": [], "leaderboard": {}, "jobs": []}
        availability["irl"] = False

    sources["ise"] = _safe(
        lambda: {
            "simulations": __import__(
                "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
            )
            .get_ise()
            .store.list_simulations(limit=25),
        },
        {"simulations": []},
    )
    availability["ise"] = isinstance(sources["ise"], dict)

    sources["cvf"] = _store_snapshot(
        "app.domain.continuous_validation_framework", "get_cvf"
    )
    availability["cvf"] = bool(sources["cvf"])

    sources["irap"] = _store_snapshot(
        "app.domain.institutional_risk_analytics", "get_irap"
    )
    availability["irap"] = bool(sources["irap"])

    sources["aqs"] = _safe(
        lambda: {
            "recommendations": __import__(
                "app.application.services.ai_quant_scientist",
                fromlist=["aqs_list_recommendations"],
            )
            .aqs_list_recommendations(limit=40)
            .get("recommendations")
            or [],
        },
        {"recommendations": []},
    )
    availability["aqs"] = isinstance(sources["aqs"], dict)

    sources["qkg"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["qkg"] = bool(sources["qkg"])

    sources["portfolio"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_portfolio_analytics",
            fromlist=["build_institutional_portfolio_analytics"],
        ).build_institutional_portfolio_analytics(days=90),
        {},
    )
    availability["portfolio"] = bool(sources["portfolio"])

    sources["sic"] = _safe(
        lambda: __import__(
            "app.application.services.strategy_intelligence_center",
            fromlist=["build_strategy_intelligence_center"],
        ).build_strategy_intelligence_center(days=90),
        {},
    )
    availability["sic"] = bool(sources["sic"])

    sources["islm"] = _safe(
        lambda: {
            "registry": __import__(
                "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
            )
            .get_islm()
            .store.list_strategies(limit=20),
        },
        {"registry": []},
    )
    availability["islm"] = isinstance(sources["islm"], dict)

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
