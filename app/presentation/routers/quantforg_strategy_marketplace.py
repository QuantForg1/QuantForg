"""QuantForg Strategy Marketplace & Registry API — read-only.

Prefix: /qsmr
Never executes trades, modifies strategies/production, approves
certifications, or deploys strategies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qsmr", tags=["quantforg-strategy-marketplace"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_strategies": True,
        "never_modifies_production": True,
        "never_approves_certifications": True,
        "never_deploys_strategies": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def qsmr_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import (
        build_qsmr_dashboard,
    )

    payload = build_qsmr_dashboard()
    payload.update(_flags())
    return payload


@router.get("/registry")
def qsmr_registry(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import qsmr_registry

    payload = qsmr_registry(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/strategies/{strategy_id}")
def qsmr_strategy(strategy_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import qsmr_strategy

    payload = qsmr_strategy(strategy_id)
    payload.update(_flags())
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail="strategy_not_found")
    return payload


@router.get("/search")
def qsmr_search(
    _user: CurrentUser,
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    lifecycle: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    certification_status: str | None = Query(default=None),
    sort_by: str = Query(default="overall_strategy_score"),
    sort_dir: str = Query(default="desc"),
    group_by: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import qsmr_search

    payload = qsmr_search(
        q=q,
        status=status,
        lifecycle=lifecycle,
        owner=owner,
        certification_status=certification_status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        group_by=group_by,
        limit=limit,
    )
    payload.update(_flags())
    return payload


@router.get("/compare")
def qsmr_compare(
    _user: CurrentUser,
    ids: str | None = Query(
        default=None, description="Comma-separated strategy IDs"
    ),
) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import qsmr_compare

    strategy_ids = [p.strip() for p in (ids or "").split(",") if p.strip()] or None
    payload = qsmr_compare(strategy_ids=strategy_ids)
    payload.update(_flags())
    return payload


@router.get("/evidence")
def qsmr_evidence(
    _user: CurrentUser,
    strategy_id: str | None = Query(default=None),
) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import qsmr_evidence

    payload = qsmr_evidence(strategy_id)
    payload.update(_flags())
    return payload


@router.get("/reports")
def qsmr_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.quantforg_strategy_marketplace import (
        qsmr_list_reports,
    )

    payload = qsmr_list_reports(limit=limit)
    payload.update(_flags())
    return payload
