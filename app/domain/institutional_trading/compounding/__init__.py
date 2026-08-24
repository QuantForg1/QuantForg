"""Aggressive compounding engine — SHADOW / OBSERVE only."""

from app.domain.institutional_trading.compounding.engine import (
    evaluate_compounding_shadow,
)
from app.domain.institutional_trading.compounding.models import (
    BROKER_MIN_LOT,
    HARD_MAX_RISK_PCT,
    LIVE_ACTIVATION,
    CompoundingInputs,
    CompoundingObservation,
)
from app.domain.institutional_trading.compounding.observe import (
    get_compounding_shadow_store,
)

__all__ = [
    "BROKER_MIN_LOT",
    "HARD_MAX_RISK_PCT",
    "LIVE_ACTIVATION",
    "CompoundingInputs",
    "CompoundingObservation",
    "evaluate_compounding_shadow",
    "get_compounding_shadow_store",
]
