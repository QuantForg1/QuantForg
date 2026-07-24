"""Reliability Engineering Suite API — read-only platform reliability.

Prefix: /res
Never executes trades or modifies strategy, thresholds, risk, safety,
OMS, gateway, scheduler, or production data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/res", tags=["reliability-engineering-suite"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "reliability_engineering_read_only": True,
    }


@router.get("/dashboard")
def res_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    payload = build_res_dashboard()
    payload.update(_flags())
    return payload


@router.get("/health")
def res_health(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {
        "platform_health": pack.get("platform_health"),
        "services": pack.get("services"),
        **_flags(),
    }


@router.get("/services")
def res_services(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"services": pack.get("services"), **_flags()}


@router.get("/availability")
def res_availability(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"availability": pack.get("availability_windows"), **_flags()}


@router.get("/recovery")
def res_recovery(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"recovery": pack.get("recovery"), **_flags()}


@router.get("/failures")
def res_failures(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"failures": pack.get("failures"), **_flags()}


@router.get("/trends")
def res_trends(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"trends": pack.get("trends"), **_flags()}


@router.get("/score")
def res_score(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"reliability_score": pack.get("reliability_score"), **_flags()}


@router.get("/evidence")
def res_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import build_res_dashboard

    pack = build_res_dashboard()
    return {"evidence": pack.get("evidence"), **_flags()}


@router.get("/reports")
def res_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.reliability_engineering_suite import res_list_reports

    payload = res_list_reports(limit=limit)
    payload.update(_flags())
    return payload
