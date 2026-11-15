"""Application facade — Phase 6 Institutional Intelligence."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_intelligence import MODEL_VERSION, isolation_payload
from app.domain.institutional_intelligence.overview import (
    build_data_quality_overview,
    build_decision_overview,
    build_execution_overview,
    build_hub_summary,
    build_market_overview,
    build_portfolio_overview,
    build_reports_overview,
    build_risk_overview,
    build_strategy_overview,
)
from app.domain.institutional_intelligence.recommendations import (
    get_recommendation_store,
)


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model_version": MODEL_VERSION,
        "order_send": False,
        "auto_live_deploy": False,
        "auto_rebalance": False,
        **isolation_payload(),
    }


def summary() -> dict[str, Any]:
    return build_hub_summary()


def market_overview(**kwargs: Any) -> dict[str, Any]:
    return build_market_overview(**kwargs)


def strategy_overview(**kwargs: Any) -> dict[str, Any]:
    return build_strategy_overview(**kwargs)


def risk_overview(**kwargs: Any) -> dict[str, Any]:
    return build_risk_overview(**kwargs)


def portfolio_overview(**kwargs: Any) -> dict[str, Any]:
    return build_portfolio_overview(**kwargs)


def execution_overview(**kwargs: Any) -> dict[str, Any]:
    return build_execution_overview(**kwargs)


def decision_overview() -> dict[str, Any]:
    return build_decision_overview()


def create_recommendation(**kwargs: Any) -> dict[str, Any]:
    return get_recommendation_store().create(**kwargs)


def set_recommendation_status(
    rec_id: str, *, status: str, note: str = ""
) -> dict[str, Any] | None:
    return get_recommendation_store().set_status(rec_id, status=status, note=note)


def reports_overview(**kwargs: Any) -> dict[str, Any]:
    return build_reports_overview(**kwargs)


def data_quality_overview(**kwargs: Any) -> dict[str, Any]:
    return build_data_quality_overview(**kwargs)
