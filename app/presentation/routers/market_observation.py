"""Market observation HTTP API.

Hidden until MARKET_OBSERVATION_ENABLED is true. The handler reads a
public quote and returns an observation. It does not place orders.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.application.services.market_observation import observation_from_tick_bundle
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/market-observation", tags=["market-observation"])


def _feed() -> Any:
    from app.application.services.public_market_feed import PublicMarketFeedService
    from app.presentation.dependencies.mt5 import get_mt5_market_data

    return PublicMarketFeedService(market_data=get_mt5_market_data())


@router.get("/{symbol}")
async def market_observation(symbol: str, user: CurrentUser) -> dict[str, Any]:
    """Observation for one symbol. The user id is not copied into the report."""
    del user
    if not get_settings().market_observation_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market observation is not enabled",
        )
    bundle = None
    try:
        bundle = await _feed().tick(symbol=symbol)
    except Exception as exc:
        logger.info("market_observation_unavailable", error_type=type(exc).__name__)
    return observation_from_tick_bundle(bundle, symbol=symbol)
