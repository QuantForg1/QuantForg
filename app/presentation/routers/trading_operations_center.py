"""Institutional Trading Operations Center API — advisory."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from app.application.services.trading_operations_center import (
    run_trading_operations_center,
)
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.execution import JournalDep

router = APIRouter(
    prefix="/trading-operations-center",
    tags=["trading-operations-center"],
)


def _journal_rows(journal: Any, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
    rows = journal.list_for_user(str(user_id), limit=limit)
    return [r for r in rows if isinstance(r, dict)]


def _try_evidence_pack() -> dict[str, Any]:
    try:
        from app.application.services.replay_evidence_lab import run_replay_evidence_lab
        from app.domain.replay_evidence_lab.evidence_store import get_evidence_database

        db = get_evidence_database()
        research = db.list("research")
        return run_replay_evidence_lab(
            opportunities=db.list("replay"),
            live_closed_trades=db.list("live"),
            demo_records=db.list("demo"),
            research_records=[
                r for r in research if r.get("kind") != "no_trade_counterfactual"
            ],
            use_process_store=False,
        )
    except Exception:
        return {}


def _try_ops_facts() -> dict[str, Any]:
    """Best-effort ops facts from live status — never fabricates on failure."""
    try:
        from app.application.services.auto_trading_status import (
            build_auto_trading_status,
        )
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from core.config.settings import get_settings

        plane = get_control_plane()
        snap = build_auto_trading_status(plane, settings=get_settings())
        facts = snap.facts
        live = snap.live or {}
        return {
            "gateway_connected": bool(facts.gateway_connected),
            "broker_connected": bool(facts.broker_connected),
            "mt5_logged_in": bool(
                facts.broker_connected or live.get("broker_connected")
            ),
            "market_open": bool(facts.market_data_live),
            "xauusd_ready": bool(facts.symbol_tradable),
            "risk_ready": not bool(facts.daily_loss_exceeded),
            "safety_ready": not bool(facts.emergency_stop),
            "execution_enabled": bool(facts.execution_enabled),
            "ops_mode": str(facts.ops_mode or plane.mode.value),
        }
    except Exception:
        return {}


@router.get("/dashboard")
async def itoc_dashboard(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    rows = _journal_rows(journal, str(user.id))
    return run_trading_operations_center(
        ops_facts=_try_ops_facts(),
        journal_rows=rows,
        evidence_pack=_try_evidence_pack(),
    )


@router.get("/brief")
async def itoc_brief(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = await itoc_dashboard(user, journal)
    return pack.get("daily_brief") or {"status": "unavailable"}


@router.get("/checklist")
async def itoc_checklist(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = await itoc_dashboard(user, journal)
    return pack.get("checklist") or {"status": "unavailable"}


@router.get("/end-of-day")
async def itoc_eod(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = await itoc_dashboard(user, journal)
    return pack.get("end_of_day") or {"status": "unavailable"}


@router.get("/weekly")
async def itoc_weekly(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = await itoc_dashboard(user, journal)
    return pack.get("weekly_review") or {"status": "unavailable"}


@router.get("/monthly")
async def itoc_monthly(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = await itoc_dashboard(user, journal)
    return pack.get("monthly_review") or {"status": "unavailable"}


@router.get("/alerts")
async def itoc_alerts(
    user: CurrentUser,
    journal: JournalDep,
) -> dict[str, Any]:
    pack = await itoc_dashboard(user, journal)
    return pack.get("operational_alerts") or {"status": "unavailable"}


@router.post("/analyze")
async def itoc_analyze(
    _user: CurrentUser,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict[str, Any]:
    """Offline analysis from supplied facts (demo / research ingest)."""
    return run_trading_operations_center(
        ops_facts=payload.get("ops_facts")
        if isinstance(payload.get("ops_facts"), dict)
        else None,
        expected_sessions=payload.get("expected_sessions")
        if isinstance(payload.get("expected_sessions"), list)
        else None,
        high_impact_news=payload.get("high_impact_news")
        if isinstance(payload.get("high_impact_news"), list)
        else None,
        calendar_available=payload.get("calendar_available")
        if isinstance(payload.get("calendar_available"), bool)
        else None,
        trades=payload.get("trades")
        if isinstance(payload.get("trades"), list)
        else None,
        decisions=payload.get("decisions")
        if isinstance(payload.get("decisions"), list)
        else None,
        previous_week_trades=payload.get("previous_week_trades")
        if isinstance(payload.get("previous_week_trades"), list)
        else None,
        evidence_pack=payload.get("evidence_pack")
        if isinstance(payload.get("evidence_pack"), dict)
        else None,
        performance_pack=payload.get("performance_pack")
        if isinstance(payload.get("performance_pack"), dict)
        else None,
        execution_quality=payload.get("execution_quality")
        if isinstance(payload.get("execution_quality"), dict)
        else None,
    )
