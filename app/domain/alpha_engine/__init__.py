"""QuantForg Alpha Engine V1.

Institutional market-quality scoring before execution (XAUUSD only).
Advisory only — never places orders, never invents market data,
never promises profitability, never bypasses Risk or Safety.
Integrates with Decision Center via mapped advisory inputs.
"""

from __future__ import annotations

from app.domain.alpha_engine.config import AlphaEngineConfig
from app.domain.alpha_engine.orchestrator import (
    AlphaEngine,
    AlphaEngineInput,
    AlphaEngineResult,
)

__all__ = [
    "AlphaEngine",
    "AlphaEngineConfig",
    "AlphaEngineInput",
    "AlphaEngineResult",
]
