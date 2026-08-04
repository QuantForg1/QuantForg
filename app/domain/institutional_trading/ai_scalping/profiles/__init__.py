"""Runtime scalping profiles (production default = SCALPING_V1)."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
    PROFILE_ID as SCALPING_V1_ID,
    PROFILE_VERSION as SCALPING_V1_VERSION,
    SCALPING_V1,
    build_scalping_v1_config,
)

ACTIVE_PRODUCTION_PROFILE = SCALPING_V1_ID

__all__ = [
    "ACTIVE_PRODUCTION_PROFILE",
    "SCALPING_V1",
    "SCALPING_V1_ID",
    "SCALPING_V1_VERSION",
    "build_scalping_v1_config",
]
