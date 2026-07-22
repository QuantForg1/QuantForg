"""Institutional Audit Trail & Governance API — governance only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import PlainTextResponse

from app.application.services.audit_governance import (
    record_audit_event,
    record_config_change,
    record_trade_versions,
    run_audit_governance,
)
from app.domain.audit_governance.change_history import get_config_change_history
from app.domain.audit_governance.reports import build_forensic_timeline
from app.domain.audit_governance.store import get_audit_store
from app.domain.audit_governance.versions import get_trade_version_registry
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/audit-governance",
    tags=["audit-governance"],
)


@router.get("/dashboard")
async def governance_dashboard(_user: CurrentUser) -> dict[str, Any]:
    pack = run_audit_governance()
    return pack.get("dashboard") or pack


@router.get("/events")
async def list_events(
    _user: CurrentUser,
    limit: int = Query(default=200, ge=1, le=2000),
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    q: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
) -> dict[str, Any]:
    rows = get_audit_store().list(
        limit=limit,
        category=category,
        severity=severity,
        actor=actor,
        action=action,
        q=q,
        since=since,
        until=until,
    )
    return {
        "status": "available",
        "count": len(rows),
        "items": rows,
        "immutable": True,
        "append_only": True,
    }


@router.post("/events")
async def create_event(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Append an immutable audit event. Never mutates trading behaviour."""
    return {"status": "recorded", "event": record_audit_event(payload)}


@router.get("/timeline")
async def forensic_timeline(
    _user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    events = get_audit_store().list(limit=limit)
    return build_forensic_timeline(events, limit=limit)


@router.get("/change-history")
async def change_history(
    _user: CurrentUser,
    limit: int = Query(default=200, ge=1, le=2000),
    scope: str | None = Query(default=None),
) -> dict[str, Any]:
    rows = get_config_change_history().list(limit=limit, scope=scope)
    return {
        "status": "available",
        "count": len(rows),
        "items": rows,
        "never_overwrite_history": True,
    }


@router.post("/change-history")
async def create_change(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    return {"status": "recorded", "change": record_config_change(payload)}


@router.get("/trade-versions")
async def trade_versions(
    _user: CurrentUser,
    trade_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    rows = get_trade_version_registry().list(limit=limit, trade_id=trade_id)
    return {"status": "available", "count": len(rows), "items": rows}


@router.post("/trade-versions")
async def create_trade_versions(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    return {"status": "recorded", "record": record_trade_versions(payload)}


@router.get("/accountability")
async def accountability(_user: CurrentUser) -> dict[str, Any]:
    pack = run_audit_governance()
    return pack.get("accountability") or {"status": "unavailable"}


@router.get("/security")
async def security_status(_user: CurrentUser) -> dict[str, Any]:
    return get_audit_store().security_status()


@router.get("/reports")
async def governance_reports(_user: CurrentUser) -> dict[str, Any]:
    pack = run_audit_governance()
    return {
        "status": "available",
        "reports": pack.get("reports"),
        "recommendations": pack.get("recommendations"),
        "hard_locks": pack.get("hard_locks"),
    }


@router.get("/export")
async def export_events(
    _user: CurrentUser,
    limit: int = Query(default=500, ge=1, le=5000),
    category: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
) -> PlainTextResponse:
    import json
    from datetime import UTC, datetime

    rows = get_audit_store().list(
        limit=limit, category=category, since=since, until=until
    )
    body = json.dumps(
        {
            "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "count": len(rows),
            "items": rows,
            "immutable": True,
        },
        indent=2,
    )
    return PlainTextResponse(
        body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                'attachment; filename="audit_governance_export.json"'
            )
        },
    )
