"""Institutional Observability Platform API — monitoring only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query

from app.application.services.institutional_observability import run_observability
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.execution import JournalDep

router = APIRouter(
    prefix="/institutional-observability",
    tags=["institutional-observability"],
)


@router.get("/dashboard")
async def observability_dashboard(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    return run_observability(journal=journal, user_id=str(user.id))


@router.get("/health")
async def system_health(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("health") or {"status": "unavailable"}


@router.get("/latency")
async def latency(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("latencies") or {"status": "unavailable"}


@router.get("/resources")
async def resources(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("resources") or {"status": "unavailable"}


@router.get("/errors")
async def errors(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("errors") or {"status": "unavailable"}


@router.get("/uptime")
async def uptime(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("uptime") or {"status": "unavailable"}


@router.get("/dependency")
async def dependency_map(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("dependency") or {"status": "unavailable"}


@router.get("/alerts")
async def alerts(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return pack.get("alerts") or {"status": "unavailable"}


@router.get("/reports")
async def reports(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = run_observability(journal=journal, user_id=str(user.id))
    return {
        "status": "available",
        "reports": pack.get("reports"),
        "recommendations": pack.get("recommendations"),
        "hard_locks": pack.get("hard_locks"),
        "observability_only": True,
    }


@router.post("/analyze")
async def analyze(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
    include_live: bool = Query(default=False),
) -> dict[str, Any]:
    """Analyze supplied observability samples (copies only)."""
    ops_facts = (
        payload.get("ops_facts")
        if isinstance(payload.get("ops_facts"), dict)
        else None
    )
    latency = (
        payload.get("latency_samples")
        if isinstance(payload.get("latency_samples"), dict)
        else None
    )
    events = (
        payload.get("error_events")
        if isinstance(payload.get("error_events"), list)
        else None
    )
    if include_live and ops_facts is None:
        return run_observability(
            latency_samples=latency,  # type: ignore[arg-type]
            error_events=events,
        )
    return run_observability(
        ops_facts=ops_facts,
        latency_samples=latency,  # type: ignore[arg-type]
        error_events=events if events is not None else [],
    )
