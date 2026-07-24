"""Application facade — QuantForg Portfolio Manager (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_portfolio_manager import get_qpm
from app.domain.quantforg_portfolio_manager.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_changes_strategy_parameters": True,
        "never_rebalances_automatically": True,
        "never_allocates_capital_automatically": True,
        "human_approval_required_for_actions": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qpm_dashboard() -> dict[str, Any]:
    payload = get_qpm().dashboard()
    payload.update(_flags())
    return payload


def qpm_allocation() -> dict[str, Any]:
    pack = get_qpm().dashboard()
    return {
        "capital_allocation": pack.get("capital_allocation"),
        "portfolio_exposure": pack.get("portfolio_exposure"),
        **_flags(),
    }


def qpm_ranking() -> dict[str, Any]:
    pack = get_qpm().dashboard()
    return {"strategy_ranking": pack.get("strategy_ranking") or [], **_flags()}


def qpm_diversification() -> dict[str, Any]:
    pack = get_qpm().dashboard()
    return {
        "diversification_matrix": (pack.get("sections") or {}).get(
            "diversification_matrix"
        ),
        **_flags(),
    }


def qpm_metrics() -> dict[str, Any]:
    pack = get_qpm().dashboard()
    return {
        "metrics": pack.get("metrics"),
        "portfolio_health": pack.get("portfolio_health"),
        "portfolio_readiness": pack.get("portfolio_readiness"),
        **_flags(),
    }


def qpm_recommendations() -> dict[str, Any]:
    pack = get_qpm().dashboard()
    return {"recommendations": pack.get("recommendations") or [], **_flags()}


def qpm_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_qpm().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}
