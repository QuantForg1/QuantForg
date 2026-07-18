"""Trading Ecosystem API — workflow OS (advisory only).

Never order_send. Never bypasses Decision Engine or EXECUTION_ENABLED.
Never modifies broker state. No DB schema.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.ecosystem import EcosystemSvc

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])


class JournalEntryRequest(BaseModel):
    id: str | None = None
    symbol: str | None = Field(default=None, max_length=32)
    screenshot_ref: str | None = None
    market_context: dict[str, Any] = Field(default_factory=dict)
    decision_engine_score: float | None = None
    decision_signal_id: str | None = None
    decision: str | None = None
    ai_review: str | None = None
    risk: dict[str, Any] = Field(default_factory=dict)
    emotion: str | None = None
    emotion_notes: str = ""
    lessons_learned: str = ""
    tags: list[str] = Field(default_factory=list)
    pnl: float | None = None
    source: str | None = None
    source_id: str | None = None


class PlaybookRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="Untitled playbook", max_length=128)
    rules: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    psychology: list[str] = Field(default_factory=list)
    risk_rules: list[str] = Field(default_factory=list)
    sessions: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    notes: str = ""


class WatchlistRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="Favorites", max_length=128)
    category: str = Field(default="general", max_length=64)
    symbols: list[str] = Field(default_factory=list)
    favorites: list[str] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class WorkspaceRequest(BaseModel):
    id: str | None = None
    name: str = Field(default="My layout", max_length=128)
    layout: dict[str, Any] = Field(default_factory=dict)
    panels: list[str] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    widgets: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)


class AlertRequest(BaseModel):
    category: str = Field(default="paper", max_length=32)
    title: str = Field(default="Alert", max_length=200)
    message: str = Field(default="", max_length=2000)
    symbol: str | None = None
    severity: str = Field(default="info", max_length=16)


class LessonRequest(BaseModel):
    lesson_id: str = Field(..., max_length=64)


class PreferencesRequest(BaseModel):
    theme: str | None = None
    language: str | None = None
    timezone: str | None = None
    hotkeys_enabled: bool | None = None
    hotkeys: dict[str, str] | None = None
    default_layout: str | None = None
    density: str | None = None


class SyncImportRequest(BaseModel):
    bundle: dict[str, Any] = Field(default_factory=dict)


@router.get("/hub")
async def ecosystem_hub(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return await eco.hub(user_id=user.id)


@router.get("/journal")
async def journal_list(
    user: CurrentUser,
    eco: EcosystemSvc,
    q: str = Query(default=""),
    tag: str | None = Query(default=None),
) -> dict[str, Any]:
    return eco.journal_list(user_id=user.id, query=q, tag=tag)


@router.post("/journal")
async def journal_upsert(
    body: JournalEntryRequest,
    user: CurrentUser,
    eco: EcosystemSvc,
) -> dict[str, Any]:
    return eco.journal_upsert(user_id=user.id, body=body.model_dump())


@router.post("/journal/ingest-paper")
async def journal_ingest_paper(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.journal_ingest_paper(user_id=user.id)


@router.get("/playbooks")
async def playbooks(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.playbooks(user_id=user.id)


@router.post("/playbooks")
async def playbook_save(
    body: PlaybookRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.playbook_save(user_id=user.id, body=body.model_dump())


@router.get("/coach")
async def performance_coach(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.coach(user_id=user.id)


@router.get("/watchlists")
async def watchlists(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.watchlists(user_id=user.id)


@router.post("/watchlists")
async def watchlist_save(
    body: WatchlistRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.watchlist_save(user_id=user.id, body=body.model_dump())


@router.get("/workspaces")
async def workspaces(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.workspaces(user_id=user.id)


@router.post("/workspaces")
async def workspace_save(
    body: WorkspaceRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.workspace_save(user_id=user.id, body=body.model_dump())


@router.get("/alerts")
async def alerts(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.alerts(user_id=user.id)


@router.post("/alerts")
async def alert_create(
    body: AlertRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.alert_create(user_id=user.id, body=body.model_dump())


@router.post("/alerts/{alert_id}/read")
async def alert_read(
    alert_id: str, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.alert_read(user_id=user.id, alert_id=alert_id)


@router.get("/learning")
async def learning(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.learning(user_id=user.id)


@router.post("/learning/complete")
async def learning_complete(
    body: LessonRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.learning_complete(user_id=user.id, lesson_id=body.lesson_id)


@router.get("/reports")
async def reports(
    user: CurrentUser,
    eco: EcosystemSvc,
    period: str = Query(default="weekly"),
) -> dict[str, Any]:
    return eco.report(user_id=user.id, period=period)


@router.get("/preferences")
async def preferences_get(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.preferences_get(user_id=user.id)


@router.post("/preferences")
async def preferences_set(
    body: PreferencesRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return eco.preferences_set(user_id=user.id, updates=updates)


@router.get("/sync/status")
async def sync_status(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.sync_status(user_id=user.id)


@router.post("/sync/export")
async def sync_export(user: CurrentUser, eco: EcosystemSvc) -> dict[str, Any]:
    return eco.sync_export(user_id=user.id)


@router.post("/sync/import")
async def sync_import(
    body: SyncImportRequest, user: CurrentUser, eco: EcosystemSvc
) -> dict[str, Any]:
    return eco.sync_import(user_id=user.id, bundle=body.bundle)
