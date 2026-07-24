"""QuantForg Certification Suite API — read-only institutional quality gate.

Prefix: /qcs
Never executes trades or modifies production, strategies, risk or safety.
Never approves releases automatically.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qcs", tags=["quantforg-certification-suite"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_modifies_risk": True,
        "never_modifies_safety": True,
        "never_approves_releases_automatically": True,
        "human_approval_required_for_certification": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def qcs_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import (
        build_qcs_dashboard,
    )

    payload = build_qcs_dashboard()
    payload.update(_flags())
    return payload


@router.get("/readiness")
def qcs_readiness(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_readiness

    payload = qcs_readiness()
    payload.update(_flags())
    return payload


@router.get("/scores")
def qcs_scores(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_scores

    payload = qcs_scores()
    payload.update(_flags())
    return payload


@router.get("/checks")
def qcs_checks(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_checks

    payload = qcs_checks()
    payload.update(_flags())
    return payload


@router.get("/blockers")
def qcs_blockers(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_blockers

    payload = qcs_blockers()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def qcs_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_evidence

    payload = qcs_evidence()
    payload.update(_flags())
    return payload


@router.get("/timeline")
def qcs_timeline(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_timeline

    payload = qcs_timeline()
    payload.update(_flags())
    return payload


@router.get("/reports")
def qcs_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_certification_suite import qcs_list_reports

    payload = qcs_list_reports(limit=limit)
    payload.update(_flags())
    return payload
