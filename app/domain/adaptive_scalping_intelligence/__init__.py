"""QuantForg Adaptive Scalping Intelligence (ASI).

Advisory market intelligence and explainability for XAUUSD scalping.
Never modifies Execution Pipeline, Auto Trading loop, Decision, Risk, or Safety.
Never fabricates statistics; reports insufficient history instead of guessing.
"""

from __future__ import annotations

from app.domain.adaptive_scalping_intelligence.config import AsiConfig
from app.domain.adaptive_scalping_intelligence.orchestrator import (
    AdaptiveScalpingIntelligence,
)
from app.domain.adaptive_scalping_intelligence.types import AsiInput

__all__ = ["AdaptiveScalpingIntelligence", "AsiConfig", "AsiInput"]
