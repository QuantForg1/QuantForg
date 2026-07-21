"""QuantForg Institutional Trading Brain V3.

Highest-level orchestration for disciplined decision-making and capital
preservation. Uses existing Decision Center, Risk, Safety, and Execution
Pipeline. Never invents market data. May recommend No Trade. Never promises
profitability or eliminates losses.
"""

from __future__ import annotations

from app.domain.trading_brain_v3.config import TradingBrainConfig
from app.domain.trading_brain_v3.orchestrator import TradingBrainV3
from app.domain.trading_brain_v3.types import BrainInput

__all__ = ["BrainInput", "TradingBrainConfig", "TradingBrainV3"]
