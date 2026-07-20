"""Phase E façade — Institutional Research Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.research.analytics import ResearchAnalyticsEngine
from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.dashboard import OperatorDashboard
from app.domain.institutional_trading.research.models import (
    PromotionReport,
    ResearchBar,
    SimulationResult,
)
from app.domain.institutional_trading.research.monte_carlo import (
    MonteCarloEngine,
    MonteCarloReport,
)
from app.domain.institutional_trading.research.optimization import (
    GridSearchOptimizer,
    ParameterSet,
)
from app.domain.institutional_trading.research.promotion import PromotionGate
from app.domain.institutional_trading.research.replay import HistoricalReplayController
from app.domain.institutional_trading.research.simulation_engine import (
    SignalProvider,
    SimulationEngine,
)
from app.domain.institutional_trading.research.trade_replay import TradeReplayEngine
from app.domain.institutional_trading.research.versioning import StrategyVersionStore
from app.domain.institutional_trading.research.walk_forward import (
    WalkForwardEngine,
    WalkForwardReport,
)


@dataclass
class InstitutionalResearchPlatform:
    """Complete research surface: sim → analytics → WF/MC → optimize → promote."""

    config: ResearchConfig = field(default_factory=lambda: DEFAULT_RESEARCH_CONFIG)
    simulation: SimulationEngine = field(default_factory=SimulationEngine)
    walk_forward: WalkForwardEngine = field(default_factory=WalkForwardEngine)
    monte_carlo: MonteCarloEngine = field(default_factory=MonteCarloEngine)
    optimizer: GridSearchOptimizer = field(default_factory=GridSearchOptimizer)
    promotion: PromotionGate = field(default_factory=PromotionGate)
    versions: StrategyVersionStore = field(default_factory=StrategyVersionStore)
    dashboard: OperatorDashboard = field(default_factory=OperatorDashboard)
    trade_replay: TradeReplayEngine = field(default_factory=TradeReplayEngine)
    analytics: ResearchAnalyticsEngine = field(default_factory=ResearchAnalyticsEngine)

    def __post_init__(self) -> None:
        self.simulation.config = self.config
        self.walk_forward.config = self.config
        self.walk_forward.simulation = self.simulation
        self.monte_carlo.config = self.config
        self.optimizer.config = self.config
        self.optimizer.simulation = self.simulation
        self.promotion.config = self.config

    def run_simulation(
        self,
        bars: list[ResearchBar],
        signal_provider: SignalProvider,
        *,
        persist: bool = True,
        meta: dict[str, Any] | None = None,
    ) -> SimulationResult:
        result = self.simulation.run(bars, signal_provider=signal_provider)
        if persist:
            self.versions.append(result, meta=meta)
        return result

    def run_walk_forward(
        self,
        bars: list[ResearchBar],
        signal_provider: SignalProvider,
        **kwargs: Any,
    ) -> WalkForwardReport:
        return self.walk_forward.run(bars, signal_provider, **kwargs)

    def run_monte_carlo(
        self,
        result: SimulationResult,
        *,
        iterations: int = 1000,
        seed: int = 42,
    ) -> MonteCarloReport:
        return self.monte_carlo.run(
            list(result.trades),
            iterations=iterations,
            seed=seed,
            initial_balance=self.config.initial_balance,
        )

    def optimize(self, bars: list[ResearchBar], **kwargs: Any) -> list[ParameterSet]:
        return self.optimizer.run(bars, **kwargs)

    def evaluate_promotion(
        self,
        result: SimulationResult,
        *,
        walk_forward: WalkForwardReport | None = None,
        monte_carlo: MonteCarloReport | None = None,
    ) -> PromotionReport:
        return self.promotion.evaluate(
            result.analytics,
            walk_forward=walk_forward,
            monte_carlo=monte_carlo,
        )

    def operator_dashboard(self) -> dict[str, Any]:
        # Reconstruct SimulationResult stubs from store is heavy; use live list API
        return {
            "stored_runs": self.versions.list(limit=50),
            "count": self.versions.count(),
        }

    def new_replay(self, bars: list[ResearchBar]) -> HistoricalReplayController:
        ctrl = HistoricalReplayController()
        ctrl.load(bars)
        return ctrl
