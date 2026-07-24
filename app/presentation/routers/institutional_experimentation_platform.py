"""Institutional Experimentation Platform API — read-only research governance.

Prefix: /iep
Never executes trades or modifies production/strategies.
Never auto-approves or auto-promotes experiments.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/iep", tags=["institutional-experimentation-platform"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_approves_experiments_automatically": True,
        "never_promotes_experiments_automatically": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def iep_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        build_iep_dashboard,
    )

    payload = build_iep_dashboard()
    payload.update(_flags())
    return payload


@router.get("/registry")
def iep_registry(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_registry,
    )

    payload = iep_registry(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/experiments/{experiment_id}")
def iep_experiment(experiment_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_experiment,
    )

    payload = iep_experiment(experiment_id)
    payload.update(_flags())
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail="experiment_not_found")
    return payload


@router.get("/hypothesis")
def iep_hypothesis(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_hypothesis,
    )

    payload = iep_hypothesis()
    payload.update(_flags())
    return payload


@router.get("/comparison")
def iep_comparison(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_comparison,
    )

    payload = iep_comparison()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def iep_evidence(
    _user: CurrentUser,
    experiment_id: str | None = Query(default=None),
) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_evidence,
    )

    payload = iep_evidence(experiment_id)
    payload.update(_flags())
    return payload


@router.get("/decisions")
def iep_decisions(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_decisions,
    )

    payload = iep_decisions()
    payload.update(_flags())
    return payload


@router.get("/statistics")
def iep_statistics(
    _user: CurrentUser,
    experiment_id: str | None = Query(default=None),
) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_statistics,
    )

    payload = iep_statistics(experiment_id)
    payload.update(_flags())
    return payload


@router.get("/reports")
def iep_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_experimentation_platform import (
        iep_list_reports,
    )

    payload = iep_list_reports(limit=limit)
    payload.update(_flags())
    return payload
