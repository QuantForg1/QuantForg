"""Trust Engine HTTP API.

Read-only. The route is hidden until TRUST_ENGINE_ENABLED is true.
It never accepts an account scope from the client, so a caller cannot
label backtest or demo results as verified live performance.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.application.services.trust_engine import load_trust_performance
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings

router = APIRouter(prefix="/trust", tags=["trust-engine"])


def _reader() -> tuple[Any, Any]:
    from app.application.use_cases.portfolio import GetAccountSnapshotUseCase
    from app.presentation.dependencies.portfolio import (
        get_history,
        get_mt5_uow_factory,
        get_portfolio_sync_service,
    )

    history = get_history()
    account = GetAccountSnapshotUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )
    return history, account


@router.get("/performance")
async def trust_performance(user: CurrentUser) -> dict[str, Any]:
    """Verified performance for the authenticated user only."""
    if not get_settings().trust_engine_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trust Engine is not enabled",
        )
    history, account = _reader()
    return await load_trust_performance(
        user_id=user.id,
        history=history,
        account=account,
    )
