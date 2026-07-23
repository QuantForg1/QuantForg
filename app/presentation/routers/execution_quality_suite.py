"""Execution Quality Suite API — read-only execution intelligence.

Prefix: /eqs
Never executes trades or modifies strategy, thresholds, risk, safety,
OMS, gateway, scheduler, production data, or research.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/eqs", tags=["execution-quality-suite"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "execution_intelligence_read_only": True,
    }


@router.get("/dashboard")
def eqs_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    payload = build_eqs_dashboard()
    payload.update(_flags())
    return payload


@router.get("/latency")
def eqs_latency(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"latency": pack.get("latency"), **_flags()}


@router.get("/slippage")
def eqs_slippage(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"slippage": pack.get("slippage"), **_flags()}


@router.get("/timelines")
def eqs_timelines(
    _user: CurrentUser,
    limit: int = Query(default=40, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    rows = (pack.get("timelines") or [])[:limit]
    return {"timelines": rows, "count": len(rows), **_flags()}


@router.get("/fill-quality")
def eqs_fill_quality(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"fill_quality": pack.get("fill_quality"), **_flags()}


@router.get("/consistency")
def eqs_consistency(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"consistency": pack.get("consistency"), **_flags()}


@router.get("/broker-health")
def eqs_broker_health(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"broker_health": pack.get("broker_health"), **_flags()}


@router.get("/score")
def eqs_score(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"execution_score": pack.get("execution_score"), **_flags()}


@router.get("/alerts")
def eqs_alerts(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"alerts": pack.get("alerts"), **_flags()}


@router.get("/evidence")
def eqs_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import build_eqs_dashboard

    pack = build_eqs_dashboard()
    return {"evidence": pack.get("evidence"), **_flags()}


@router.get("/reports")
def eqs_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.execution_quality_suite import eqs_list_reports

    payload = eqs_list_reports(limit=limit)
    payload.update(_flags())
    return payload
