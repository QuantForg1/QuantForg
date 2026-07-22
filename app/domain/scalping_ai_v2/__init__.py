"""QuantForg Institutional XAUUSD Scalping AI V2 / V2.1 hardening.

Production-grade autonomous scalping orchestration that never bypasses
Risk, Safety, or Decision Center, never creates alternate execution paths,
prefers No Trade, and never calls order_send.

V2.1 strengthens long-running stability, state persistence, MT5 sync,
safe mode, emergency stop, latency, soak tests, and production audit —
without replacing the V2 architecture or creating a second execution loop.
"""

from __future__ import annotations

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.orchestrator import ScalpingAiV2
from app.domain.scalping_ai_v2.types import ScalpCycleInput

__all__ = ["ScalpCycleInput", "ScalpingAiV2", "ScalpingAiV2Config"]
