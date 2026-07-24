"""QuantForg Decision Intelligence Engine API — advisory read-only.

Prefix: /qdie
Never executes trades or modifies production/strategies/risk.
Never approves releases, allocates capital, or performs automatic actions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qdie", tags=["quantforg-decision-intelligence"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_modifies_risk": True,
        "never_approves_releases": True,
        "never_allocates_capital": True,
        "never_performs_automatic_actions": True,
        "human_approval_required": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def qdie_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        build_qdie_dashboard,
    )

    payload = build_qdie_dashboard()
    payload.update(_flags())
    return payload


@router.get("/recommendations")
def qdie_recommendations(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_recommendations as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/scores")
def qdie_scores(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_scores as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def qdie_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_evidence as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/tradeoffs")
def qdie_tradeoffs(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_tradeoffs as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/brief")
def qdie_brief(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_brief as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/reports")
def qdie_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_reports as svc,
    )

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/history")
def qdie_history(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.quantforg_decision_intelligence import (
        qdie_history as svc,
    )

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload
