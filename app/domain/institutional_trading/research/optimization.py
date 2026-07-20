"""Grid-search parameter optimization — top N sets; never looks ahead."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from itertools import product
from typing import Any

from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.models import ResearchBar
from app.domain.institutional_trading.research.simulation_engine import (
    RuleSignalProvider,
    SimulationEngine,
)


@dataclass(frozen=True, slots=True)
class ParameterSet:
    confluence: int
    atr_stop: Decimal
    be_r: Decimal
    trail_r: Decimal
    session: str
    risk_lots: Decimal
    score: Decimal
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "confluence": self.confluence,
            "atr_stop": str(self.atr_stop),
            "be_r": str(self.be_r),
            "trail_r": str(self.trail_r),
            "session": self.session,
            "risk_lots": str(self.risk_lots),
            "score": str(self.score),
            "metrics": dict(self.metrics),
        }


@dataclass
class GridSearchOptimizer:
    config: ResearchConfig = field(default_factory=lambda: DEFAULT_RESEARCH_CONFIG)
    simulation: SimulationEngine = field(default_factory=SimulationEngine)

    def run(
        self,
        bars: list[ResearchBar],
        *,
        confluence_grid: tuple[int, ...] = (80, 85, 90),
        atr_grid: tuple[Decimal, ...] = (Decimal("8"), Decimal("10"), Decimal("12")),
        be_grid: tuple[Decimal, ...] = (Decimal("1.0"), Decimal("1.2")),
        trail_grid: tuple[Decimal, ...] = (Decimal("2.0"), Decimal("2.5")),
        session_grid: tuple[str, ...] = ("london", "overlap"),
        risk_grid: tuple[Decimal, ...] = (Decimal("0.05"), Decimal("0.10")),
    ) -> list[ParameterSet]:
        results: list[ParameterSet] = []
        for conf, atr, be, trail, session, risk in product(
            confluence_grid, atr_grid, be_grid, trail_grid, session_grid, risk_grid
        ):
            provider = RuleSignalProvider(
                volume=risk,
                stop_distance=atr,
                take_distance=atr * trail,
            )
            # Session filter: skip signals on mismatched session labels when present
            filtered = [
                b
                for b in bars
                if not b.session or b.session == session or session == "overlap"
            ]
            if len(filtered) < 10:
                filtered = bars
            sim = self.simulation.run(filtered, signal_provider=provider)
            a = sim.analytics
            pf = a.profit_factor or Decimal("0")
            # Score: PF * expectancy_sign * (1 - dd/100) with confluence preference
            score = pf * (Decimal("1") if a.expectancy >= 0 else Decimal("0.5"))
            score = score * (Decimal("1") - a.max_drawdown_pct / Decimal("100"))
            score = score * (Decimal(conf) / Decimal("100"))
            # be_r / trail_r recorded for research (geometry via atr*trail)
            _ = be
            results.append(
                ParameterSet(
                    confluence=conf,
                    atr_stop=atr,
                    be_r=be,
                    trail_r=trail,
                    session=session,
                    risk_lots=risk,
                    score=score.quantize(Decimal("0.0001")),
                    metrics={
                        "profit_factor": str(a.profit_factor),
                        "expectancy": str(a.expectancy),
                        "max_drawdown_pct": str(a.max_drawdown_pct),
                        "trade_count": a.trade_count,
                        "win_rate": str(a.win_rate),
                    },
                )
            )
        results.sort(key=lambda p: p.score, reverse=True)
        return results[: self.config.optimization_top_n]
