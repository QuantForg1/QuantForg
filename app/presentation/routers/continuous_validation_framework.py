"""Continuous Validation Framework API — read-only evidence layer.

Prefix: /cvf
Never executes trades, modifies production, approves promotions, or
triggers automation. Humans remain responsible for every decision.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/cvf", tags=["continuous-validation-framework"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "never_approves_promotions": True,
        "humans_remain_responsible": True,
        "continuous_validation_read_only": True,
    }


@router.get("/dashboard")
def cvf_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    payload = build_cvf_dashboard()
    payload.update(_flags())
    return payload


@router.get("/replay-vs-live")
def cvf_replay_vs_live(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"replay_vs_live": pack.get("replay_vs_live"), **_flags()}


@router.get("/drift")
def cvf_drift(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"drift": pack.get("drift"), **_flags()}


@router.get("/regimes")
def cvf_regimes(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"regime_validation": pack.get("regime_validation"), **_flags()}


@router.get("/parameters")
def cvf_parameters(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"parameter_stability": pack.get("parameter_stability"), **_flags()}


@router.get("/confidence")
def cvf_confidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"confidence": pack.get("confidence"), **_flags()}


@router.get("/alerts")
def cvf_alerts(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"alerts": pack.get("alerts"), **_flags()}


@router.get("/evidence")
def cvf_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import (
        build_cvf_dashboard,
    )

    pack = build_cvf_dashboard()
    return {"evidence_chains": pack.get("evidence_chains"), **_flags()}


@router.get("/reports")
def cvf_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.continuous_validation_framework import cvf_list_reports

    payload = cvf_list_reports(limit=limit)
    payload.update(_flags())
    return payload
