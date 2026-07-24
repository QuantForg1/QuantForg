"""QPTCM gather — READ-ONLY evidence for paper-trading campaigns."""

from __future__ import annotations

from typing import Any, Callable

from app.domain.quantforg_paper_trading_campaign.models import DATA_SOURCES


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


def gather_campaign_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    sources["qsf"] = _store_snapshot(
        "app.domain.quantforg_strategy_factory", "get_qsf"
    )
    availability["qsf"] = bool(sources["qsf"])

    def _islm() -> dict[str, Any]:
        islm = __import__(
            "app.domain.institutional_strategy_lifecycle", fromlist=["get_islm"]
        ).get_islm()
        return {
            "registry": islm.store.list_strategies(limit=40),
            "approvals": islm.store.list_approvals(limit=15),
        }

    sources["islm"] = _safe(_islm, {"registry": [], "approvals": []})
    availability["islm"] = isinstance(sources["islm"], dict)

    sources["qcs"] = _store_snapshot(
        "app.domain.quantforg_certification_suite", "get_qcs"
    )
    availability["qcs"] = bool(sources["qcs"])

    sources["qdie"] = _store_snapshot(
        "app.domain.quantforg_decision_intelligence", "get_qdie"
    )
    availability["qdie"] = bool(sources["qdie"])

    sources["qsmr"] = _store_snapshot(
        "app.domain.quantforg_strategy_marketplace", "get_qsmr"
    )
    availability["qsmr"] = bool(sources["qsmr"])

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

    sources["cvf"] = _store_snapshot(
        "app.domain.continuous_validation_framework", "get_cvf"
    )
    availability["cvf"] = bool(sources["cvf"])

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
        "expected_sources": list(DATA_SOURCES),
        "read_only": True,
        "never_mutates_sources": True,
        "paper_trading_only": True,
    }
