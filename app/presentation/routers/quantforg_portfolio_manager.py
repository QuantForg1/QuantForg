"""QuantForg Portfolio Manager API — read-only portfolio orchestration.

Prefix: /qpm
Never executes trades, modifies production, changes parameters,
or rebalances/allocates automatically.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qpm", tags=["quantforg-portfolio-manager"])


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
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def qpm_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import build_qpm_dashboard

    payload = build_qpm_dashboard()
    payload.update(_flags())
    return payload


@router.get("/allocation")
def qpm_allocation(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import qpm_allocation

    payload = qpm_allocation()
    payload.update(_flags())
    return payload


@router.get("/ranking")
def qpm_ranking(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import qpm_ranking

    payload = qpm_ranking()
    payload.update(_flags())
    return payload


@router.get("/diversification")
def qpm_diversification(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import qpm_diversification

    payload = qpm_diversification()
    payload.update(_flags())
    return payload


@router.get("/metrics")
def qpm_metrics(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import qpm_metrics

    payload = qpm_metrics()
    payload.update(_flags())
    return payload


@router.get("/recommendations")
def qpm_recommendations(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import qpm_recommendations

    payload = qpm_recommendations()
    payload.update(_flags())
    return payload


@router.get("/reports")
def qpm_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_portfolio_manager import qpm_list_reports

    payload = qpm_list_reports(limit=limit)
    payload.update(_flags())
    return payload
