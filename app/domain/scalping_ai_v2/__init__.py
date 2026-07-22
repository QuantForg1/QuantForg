"""QuantForg Institutional XAUUSD Scalping AI V2.

Production-grade autonomous scalping orchestration that never bypasses
Risk, Safety, or Decision Center, never creates alternate execution paths,
prefers No Trade, and never calls order_send.
"""

from __future__ import annotations

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.orchestrator import ScalpingAiV2
from app.domain.scalping_ai_v2.types import ScalpCycleInput

__all__ = ["ScalpCycleInput", "ScalpingAiV2", "ScalpingAiV2Config"]
