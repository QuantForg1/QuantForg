"""Institutional Risk Analytics Platform API — read-only risk intelligence.

Prefix: /irap
Never executes trades or modifies production, strategy, risk parameters,
safety, or approvals.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/irap", tags=["institutional-risk-analytics"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "never_modifies_risk_parameters": True,
        "portfolio_risk_intelligence_read_only": True,
    }


@router.get("/dashboard")
def irap_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    payload = build_irap_dashboard()
    payload.update(_flags())
    return payload


@router.get("/metrics")
def irap_metrics(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {"metrics": pack.get("metrics"), **_flags()}


@router.get("/exposure")
def irap_exposure(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {
        "exposure": pack.get("exposure"),
        "concentration": pack.get("concentration"),
        "capital_allocation": pack.get("capital_allocation"),
        **_flags(),
    }


@router.get("/drawdown")
def irap_drawdown(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {"drawdown": pack.get("drawdown"), **_flags()}


@router.get("/correlation")
def irap_correlation(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {"correlation": pack.get("correlation"), **_flags()}


@router.get("/stress")
def irap_stress(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {
        "stress_loss": pack.get("stress_loss"),
        "scenario_risk": pack.get("scenario_risk"),
        "tail_risk": pack.get("tail_risk"),
        **_flags(),
    }


@router.get("/alerts")
def irap_alerts(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {"alerts": pack.get("alerts"), **_flags()}


@router.get("/trends")
def irap_trends(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import build_irap_dashboard

    pack = build_irap_dashboard()
    return {"trends": pack.get("trends"), **_flags()}


@router.get("/reports")
def irap_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_risk_analytics import irap_list_reports

    payload = irap_list_reports(limit=limit)
    payload.update(_flags())
    return payload
