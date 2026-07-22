"""QuantForg Real Market Intelligence Platform (RMIP).

Institutional intelligence layer that enriches market context from real-world
information. Never places trades, never changes trading rules, never modifies
Auto Trading, Execution, Decision, Risk, Safety, ASI, Edge Engine, Alpha Factory,
or IVP.
"""

from __future__ import annotations

from app.domain.real_market_intelligence_platform.config import RmipConfig
from app.domain.real_market_intelligence_platform.orchestrator import (
    RealMarketIntelligencePlatform,
)
from app.domain.real_market_intelligence_platform.types import RmipInput

__all__ = [
    "RealMarketIntelligencePlatform",
    "RmipConfig",
    "RmipInput",
]
