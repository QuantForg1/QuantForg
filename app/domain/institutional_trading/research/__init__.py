"""Phase E — Institutional Research Platform (simulation, analytics, promotion).

Reuses Phase A–D engines via imports/ports. Never modifies OMS or A–D.
No AI. No MT5 order_send.
"""

from __future__ import annotations

from app.domain.institutional_trading.research.analytics import ResearchAnalyticsEngine
from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.dashboard import OperatorDashboard
from app.domain.institutional_trading.research.monte_carlo import MonteCarloEngine
from app.domain.institutional_trading.research.optimization import GridSearchOptimizer
from app.domain.institutional_trading.research.promotion import PromotionGate
from app.domain.institutional_trading.research.replay import HistoricalReplayController
from app.domain.institutional_trading.research.simulation_engine import SimulationEngine
from app.domain.institutional_trading.research.versioning import StrategyVersionStore
from app.domain.institutional_trading.research.walk_forward import WalkForwardEngine

__all__ = [
    "DEFAULT_RESEARCH_CONFIG",
    "GridSearchOptimizer",
    "HistoricalReplayController",
    "MonteCarloEngine",
    "OperatorDashboard",
    "PromotionGate",
    "ResearchAnalyticsEngine",
    "ResearchConfig",
    "SimulationEngine",
    "StrategyVersionStore",
    "WalkForwardEngine",
]
