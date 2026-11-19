"""Decision evidence API — read-only projection of existing signal records.

Never places, modifies, or cancels orders. Never recalculates risk.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.application.services.decision_evidence import (
    build_decision_history,
    build_live_report,
)
from app.presentation.routers.symbol_signals import SignalsUser

router = APIRouter(prefix="/decision-evidence", tags=["decision-evidence"])


@router.get("/report")
async def decision_evidence_report(
    user: SignalsUser,
    symbol: str | None = Query(default=None, max_length=32),
) -> dict[str, Any]:
    _ = user
    return build_live_report(symbol)


@router.get("/history")
async def decision_evidence_history(
    user: SignalsUser,
    symbol: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    _ = user
    return build_decision_history(symbol=symbol, limit=limit)
