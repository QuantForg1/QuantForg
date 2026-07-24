"""QuantForg Event Mesh API — read-only event distribution.

Prefix: /qem
Never executes trades or modifies production/strategies/risk.
Never approves releases. Events are immutable.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qem", tags=["quantforg-event-mesh"])


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
        "events_immutable": True,
        "event_distribution_read_only": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def qem_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import build_qem_dashboard

    payload = build_qem_dashboard()
    payload.update(_flags())
    return payload


@router.get("/events")
def qem_events(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_events as svc

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/stream")
def qem_stream(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_stream as svc

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/timeline")
def qem_timeline(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_timeline as svc

    payload = svc(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/search")
def qem_search(
    _user: CurrentUser,
    strategy_id: str | None = Query(default=None),
    release_id: str | None = Query(default=None),
    experiment_id: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_search as svc

    payload = svc(
        strategy_id=strategy_id,
        release_id=release_id,
        experiment_id=experiment_id,
        correlation_id=correlation_id,
        category=category,
        event_type=event_type,
        q=q,
        limit=limit,
    )
    payload.update(_flags())
    return payload


@router.get("/replay")
def qem_replay(
    _user: CurrentUser,
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_replay as svc

    payload = svc(from_ts=from_ts, to_ts=to_ts, limit=limit)
    payload.update(_flags())
    return payload


@router.get("/correlation")
def qem_correlation_groups(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_correlation as svc

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/correlation/{correlation_id}")
def qem_correlation_detail(
    correlation_id: str,
    _user: CurrentUser,
) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_correlation as svc

    payload = svc(correlation_id=correlation_id)
    payload.update(_flags())
    return payload


@router.get("/subscribers")
def qem_subscribers(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_event_mesh import qem_subscribers as svc

    payload = svc()
    payload.update(_flags())
    return payload
