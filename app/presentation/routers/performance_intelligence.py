"""Institutional Performance Intelligence API — journals only; advisory."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.application.services.performance_intelligence import (
    run_performance_intelligence,
    run_period_report,
)
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.execution import JournalDep

router = APIRouter(
    prefix="/performance-intelligence",
    tags=["performance-intelligence"],
)


def _journal_as_trades(journal: Any, user_id: str, limit: int) -> list[dict[str, Any]]:
    rows = journal.list_for_user(str(user_id), limit=limit)
    return [r for r in rows if isinstance(r, dict)]


@router.get("/dashboard")
async def performance_dashboard(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=500),
    period: str = Query(default="monthly"),
) -> dict[str, Any]:
    """Full performance IQ pack from execution journal evidence."""
    rows = _journal_as_trades(journal, str(user.id), limit)
    return run_performance_intelligence(
        journal_rows=rows,
        period=period,
    )


@router.get("/sessions")
async def performance_sessions(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    from app.domain.performance_intelligence.dashboard import (
        enrich_session_analytics,
        normalize_trade_rows,
    )

    rows = normalize_trade_rows(_journal_as_trades(journal, str(user.id), limit))
    return enrich_session_analytics(rows)


@router.get("/regimes")
async def performance_regimes(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    from app.domain.performance_intelligence.dashboard import (
        enrich_regime_analytics,
        normalize_trade_rows,
    )

    rows = normalize_trade_rows(_journal_as_trades(journal, str(user.id), limit))
    return enrich_regime_analytics(rows)


@router.get("/signals")
async def performance_signals(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    from app.domain.performance_intelligence.dashboard import (
        compute_signal_analytics,
        normalize_trade_rows,
    )

    rows = normalize_trade_rows(_journal_as_trades(journal, str(user.id), limit))
    return compute_signal_analytics(rows)


@router.get("/no-trade")
async def performance_no_trade(
    _user: CurrentUser,
) -> dict[str, Any]:
    """NO_TRADE analytics — empty until decision journal is supplied."""
    from app.domain.performance_intelligence.dashboard import (
        compute_no_trade_analytics,
    )

    return compute_no_trade_analytics(None)


@router.get("/time")
async def performance_time(
    user: CurrentUser,
    journal: JournalDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    from app.domain.performance_intelligence.dashboard import (
        compute_time_analytics,
        normalize_trade_rows,
    )

    rows = normalize_trade_rows(_journal_as_trades(journal, str(user.id), limit))
    return compute_time_analytics(rows)


@router.get("/reports")
async def performance_reports(
    user: CurrentUser,
    journal: JournalDep,
    period: str = Query(default="monthly"),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    rows = _journal_as_trades(journal, str(user.id), limit)
    return run_period_report(trades=rows, period=period)
