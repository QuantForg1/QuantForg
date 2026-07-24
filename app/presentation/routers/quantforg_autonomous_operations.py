"""QuantForg Autonomous Operations Center API — read-only orchestration.

Prefix: /aoc
Never executes trades or modifies production/strategies/risk/safety.
Never approves releases, allocates capital, deploys, or remediates automatically.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/aoc", tags=["quantforg-autonomous-operations"])


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
        "never_approves_releases": True,
        "never_allocates_capital": True,
        "never_deploys_strategies": True,
        "never_performs_automatic_remediation": True,
        "human_approval_required_for_recommendations": True,
        "preserves_existing_safety_guarantees": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def aoc_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import (
        build_aoc_dashboard,
    )

    payload = build_aoc_dashboard()
    payload.update(_flags())
    return payload


@router.get("/recommendations")
def aoc_recommendations(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import (
        aoc_recommendations,
    )

    payload = aoc_recommendations()
    payload.update(_flags())
    return payload


@router.get("/queue")
def aoc_queue(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import aoc_queue

    payload = aoc_queue()
    payload.update(_flags())
    return payload


@router.get("/scores")
def aoc_scores(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import aoc_scores

    payload = aoc_scores()
    payload.update(_flags())
    return payload


@router.get("/evidence")
def aoc_evidence(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import aoc_evidence

    payload = aoc_evidence()
    payload.update(_flags())
    return payload


@router.get("/brief")
def aoc_brief(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import aoc_brief

    payload = aoc_brief()
    payload.update(_flags())
    return payload


@router.get("/reports")
def aoc_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_autonomous_operations import (
        aoc_list_reports,
    )

    payload = aoc_list_reports(limit=limit)
    payload.update(_flags())
    return payload
