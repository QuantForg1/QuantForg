"""Risk insight API. Hidden until RISK_INTELLIGENCE_ENABLED is true."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.domain.exceptions.base import NotFoundError, ServiceUnavailableError
from app.domain.risk_intelligence import RiskInsightInput, build_risk_insight
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/risk-intelligence", tags=["risk-intelligence"])


def _account() -> Any:
    from app.application.use_cases.portfolio import GetAccountSnapshotUseCase
    from app.presentation.dependencies.portfolio import (
        get_mt5_uow_factory,
        get_portfolio_sync_service,
    )

    return GetAccountSnapshotUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


@router.get("/insight")
async def risk_insight(user: CurrentUser) -> dict[str, Any]:
    """Insight for the signed-in user. It does not change risk settings."""
    if not get_settings().risk_intelligence_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk intelligence is not enabled",
        )
    now = datetime.now(UTC)
    spec = RiskInsightInput(read_at=now, source="none")
    try:
        snap = await _account().execute(user_id=user.id)
        spec = RiskInsightInput(
            read_at=now,
            source="account_snapshot",
            equity=str(snap.equity),
            balance=str(snap.balance),
            free_margin=str(snap.free_margin),
            used_margin=str(snap.margin),
            floating_pnl=str(snap.profit),
        )
    except (NotFoundError, ServiceUnavailableError) as exc:
        logger.info("risk_insight_unavailable", error_type=type(exc).__name__)
    report = build_risk_insight(spec)
    report["changes_risk_policy"] = False
    return report
