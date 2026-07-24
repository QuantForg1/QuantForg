"""Institutional Control Plane API — read-only executive operations.

Prefix: /icp
Never executes trades or modifies production, strategy, risk, releases,
experiments, or lifecycle approvals.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/icp", tags=["institutional-control-plane"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategy": True,
        "never_modifies_risk": True,
        "never_modifies_releases": True,
        "never_approves_experiments": True,
        "never_approves_lifecycle_transitions": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def icp_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import build_icp_dashboard

    payload = build_icp_dashboard()
    payload.update(_flags())
    return payload


@router.get("/health")
def icp_health(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import icp_health

    payload = icp_health()
    payload.update(_flags())
    return payload


@router.get("/alerts")
def icp_alerts(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import icp_alerts

    payload = icp_alerts()
    payload.update(_flags())
    return payload


@router.get("/timeline")
def icp_timeline(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import icp_timeline

    payload = icp_timeline()
    payload.update(_flags())
    return payload


@router.get("/dependencies")
def icp_dependencies(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import icp_dependencies

    payload = icp_dependencies()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def icp_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import icp_evidence

    payload = icp_evidence()
    payload.update(_flags())
    return payload


@router.get("/reports")
def icp_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_control_plane import icp_list_reports

    payload = icp_list_reports(limit=limit)
    payload.update(_flags())
    return payload
