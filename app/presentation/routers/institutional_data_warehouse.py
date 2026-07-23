"""Institutional Data Warehouse API — read-only analytics infrastructure."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Query
from fastapi.responses import PlainTextResponse

from app.application.services.institutional_data_warehouse import (
    ingest_domain,
    query_analytics,
    run_warehouse,
    snapshot_read_only_sources,
)
from app.domain.institutional_data_warehouse.models import DATA_DOMAINS
from app.domain.institutional_data_warehouse.store import get_warehouse
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.execution import JournalDep

router = APIRouter(
    prefix="/institutional-data-warehouse",
    tags=["institutional-data-warehouse"],
)


def _journal_rows(journal: Any, user_id: str, limit: int) -> list[dict[str, Any]]:
    rows = journal.list_for_user(str(user_id), limit=limit)
    return [r for r in rows if isinstance(r, dict)]


@router.get("/dashboard")
async def warehouse_dashboard(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    """Warehouse overview — snapshots journal read-only then aggregates."""
    snapshot_read_only_sources(
        journal_rows=_journal_rows(journal, str(user.id), limit)
    )
    return run_warehouse()


@router.get("/datasets")
async def list_datasets(_user: CurrentUser) -> dict[str, Any]:
    inv = get_warehouse().inventory()
    return {
        "status": "available",
        "domains": list(DATA_DOMAINS),
        "inventory": inv,
        "read_only": True,
    }


@router.get("/datasets/{domain}")
async def explore_dataset(
    domain: str,
    _user: CurrentUser,
    limit: int = Query(default=200, ge=1, le=2000),
    q: str | None = Query(default=None),
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    session: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    strategy_version: str | None = Query(default=None),
) -> dict[str, Any]:
    if domain not in DATA_DOMAINS:
        return {
            "status": "unavailable",
            "reason": f"Unknown domain '{domain}'",
            "allowed": list(DATA_DOMAINS),
        }
    rows = get_warehouse().list(
        domain,  # type: ignore[arg-type]
        limit=limit,
        q=q,
        since=since,
        until=until,
        session=session,
        environment=environment,
        strategy_version=strategy_version,
    )
    return {
        "status": "available",
        "domain": domain,
        "count": len(rows),
        "items": rows,
        "read_only": True,
    }


@router.post("/ingest")
async def ingest(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Ingest caller-supplied rows into a warehouse domain (copies only)."""
    domain = str(payload.get("domain") or "")
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return ingest_domain(
        domain,
        rows,
        environment=payload.get("environment"),
        replace=bool(payload.get("replace")),
    )


@router.post("/snapshot")
async def snapshot(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    return snapshot_read_only_sources(
        journal_rows=_journal_rows(journal, str(user.id), limit)
    )


@router.get("/analytics")
async def analytics(_user: CurrentUser) -> dict[str, Any]:
    return query_analytics()


@router.get("/analytics/{query}")
async def analytics_query(query: str, _user: CurrentUser) -> dict[str, Any]:
    pack = query_analytics()
    if query not in pack:
        return {
            "status": "unavailable",
            "reason": f"Unknown analytics query '{query}'",
            "allowed": [k for k in pack if k != "read_only"],
        }
    return pack[query] if isinstance(pack[query], dict) else {"result": pack[query]}


@router.get("/reports")
async def warehouse_reports(_user: CurrentUser) -> dict[str, Any]:
    pack = run_warehouse()
    return {
        "status": "available",
        "reports": pack.get("reports"),
        "recommendations": pack.get("recommendations"),
        "hard_locks": pack.get("hard_locks"),
        "read_only": True,
    }


@router.get("/dimensional")
async def warehouse_dimensional(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_data_warehouse import query_dimensional

    return query_dimensional()


@router.get("/quality")
async def warehouse_quality(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_data_warehouse import query_data_quality

    return query_data_quality()


@router.get("/retention")
async def warehouse_retention(
    _user: CurrentUser,
    apply: bool = Query(default=False),
) -> dict[str, Any]:
    from app.application.services.institutional_data_warehouse import query_retention

    return query_retention(apply=apply)


@router.get("/query/aggregate")
async def warehouse_aggregate(
    _user: CurrentUser,
    domain: str = Query(default="trades"),
    grain: str = Query(default="day"),
) -> dict[str, Any]:
    from app.application.services.institutional_data_warehouse import query_aggregation

    return query_aggregation(domain=domain, grain=grain)


@router.get("/query/rolling")
async def warehouse_rolling(
    _user: CurrentUser,
    domain: str = Query(default="trades"),
    window: int = Query(default=20, ge=2, le=200),
) -> dict[str, Any]:
    from app.application.services.institutional_data_warehouse import query_rolling

    return query_rolling(domain=domain, window=window)


@router.get("/export")
async def export_dataset(
    _user: CurrentUser,
    domain: str = Query(default="trades"),
    limit: int = Query(default=500, ge=1, le=5000),
) -> PlainTextResponse:
    import json
    from datetime import UTC, datetime

    if domain not in DATA_DOMAINS:
        body = json.dumps(
            {"status": "unavailable", "allowed": list(DATA_DOMAINS)},
            indent=2,
        )
        return PlainTextResponse(body, media_type="application/json", status_code=400)
    rows = get_warehouse().list(domain, limit=limit)  # type: ignore[arg-type]
    body = json.dumps(
        {
            "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "domain": domain,
            "count": len(rows),
            "items": rows,
            "read_only": True,
        },
        indent=2,
    )
    return PlainTextResponse(
        body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="idw_{domain}_export.json"'
            )
        },
    )
