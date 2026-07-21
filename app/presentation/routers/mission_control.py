"""Mission Control API — institutional executive dashboard (not Monitoring)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.mission_control import MissionControlService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/mission-control", tags=["mission-control"])

_service = MissionControlService()


class NoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    operator: str = "operator"


class LiveFeedsBody(BaseModel):
    """Optional client-supplied live broker feeds (never fabricated server-side)."""

    capital: dict[str, Any] | None = None
    positions: list[dict[str, Any]] | None = None
    xauusd: dict[str, Any] | None = None
    daily: dict[str, Any] | None = None


@router.get("/status")
async def mission_control_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.get("/dashboard")
async def mission_control_dashboard(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.dashboard()


@router.post("/dashboard")
async def mission_control_dashboard_with_feeds(
    body: LiveFeedsBody, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.dashboard(
        capital=body.capital,
        positions=body.positions,
        xauusd=body.xauusd,
        daily=body.daily,
    )


@router.get("/notes")
async def mission_control_notes(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.notes(limit=limit)


@router.post("/notes")
async def mission_control_add_note(
    body: NoteBody, user: CurrentUser
) -> dict[str, Any]:
    operator = str(
        getattr(user, "email", None) or getattr(user, "id", "") or "operator"
    )
    return _service.add_note(body.text, operator=operator, tags=body.tags)


@router.get("/search")
async def mission_control_search(
    user: CurrentUser,
    q: str = Query(default="", max_length=200),
) -> dict[str, Any]:
    _ = user
    return _service.search(q)
