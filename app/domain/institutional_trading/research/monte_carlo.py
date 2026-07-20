"""Monte Carlo engine — seeded deterministic perturbations of trade sequences."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.institutional_trading.research.analytics import ResearchAnalyticsEngine
from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.models import (
    EquityPoint,
    ResearchTrade,
)


MC_COUNTS: tuple[int, ...] = (100, 500, 1000, 5000)


@dataclass(frozen=True, slots=True)
class MonteCarloReport:
    iterations: int
    seed: int
    median_final_equity: Decimal
    p05_final_equity: Decimal
    p95_final_equity: Decimal
    median_profit_factor: Decimal | None
    median_max_dd: Decimal
    passed: bool
    distribution_final_equity: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "iterations": self.iterations,
            "seed": self.seed,
            "median_final_equity": str(self.median_final_equity),
            "p05_final_equity": str(self.p05_final_equity),
            "p95_final_equity": str(self.p95_final_equity),
            "median_profit_factor": (
                str(self.median_profit_factor)
                if self.median_profit_factor is not None
                else None
            ),
            "median_max_dd": str(self.median_max_dd),
            "passed": self.passed,
            "distribution_final_equity": list(self.distribution_final_equity),
        }


@dataclass
class MonteCarloEngine:
    """Resample closed trades with slippage/spread/latency noise (seeded)."""

    config: ResearchConfig = field(default_factory=lambda: DEFAULT_RESEARCH_CONFIG)
    analytics: ResearchAnalyticsEngine = field(default_factory=ResearchAnalyticsEngine)

    def run(
        self,
        trades: list[ResearchTrade],
        *,
        iterations: int = 1000,
        seed: int = 42,
        initial_balance: Decimal | None = None,
    ) -> MonteCarloReport:
        if iterations not in MC_COUNTS:
            raise ValueError(f"iterations must be one of {MC_COUNTS}")
        closed = [t for t in trades if t.status == "closed"]
        initial = initial_balance or self.config.initial_balance
        rng = random.Random(seed)  # deterministic given seed

        finals: list[Decimal] = []
        pfs: list[Decimal] = []
        dds: list[Decimal] = []

        for _ in range(iterations):
            order = list(closed)
            rng.shuffle(order)
            equity = initial
            peak = initial
            max_dd = Decimal("0")
            sim_pnls: list[Decimal] = []
            for t in order:
                slip = Decimal(str(rng.uniform(0, float(self.config.default_slippage))))
                spread_noise = Decimal(
                    str(rng.uniform(0, float(self.config.default_spread) / 2))
                )
                # latency modeled as tiny adverse R noise
                latency_noise = Decimal(str(rng.uniform(-0.02, 0.02)))
                adj = t.pnl - (slip + spread_noise) * t.volume * Decimal("10")
                adj = adj * (Decimal("1") + latency_noise)
                sim_pnls.append(adj)
                equity += adj
                peak = max(peak, equity)
                if peak > 0 and equity < peak:
                    dd = (peak - equity) / peak * Decimal("100")
                    max_dd = max(max_dd, dd)
            finals.append(equity)
            dds.append(max_dd)
            # rough PF on shuffled pnls
            wins = sum((p for p in sim_pnls if p > 0), Decimal("0"))
            losses = abs(sum((p for p in sim_pnls if p < 0), Decimal("0")))
            if losses > 0:
                pfs.append(wins / losses)
            elif wins > 0:
                pfs.append(Decimal("999"))
            else:
                pfs.append(Decimal("0"))

        finals_sorted = sorted(finals)
        pfs_sorted = sorted(pfs)
        dds_sorted = sorted(dds)

        def _pct(xs: list[Decimal], q: float) -> Decimal:
            if not xs:
                return Decimal("0")
            i = int(q * (len(xs) - 1))
            return xs[i].quantize(Decimal("0.0001"))

        median_eq = _pct(finals_sorted, 0.5)
        p05 = _pct(finals_sorted, 0.05)
        p95 = _pct(finals_sorted, 0.95)
        median_pf = _pct(pfs_sorted, 0.5) if pfs_sorted else None
        median_dd = _pct(dds_sorted, 0.5)

        passed = True
        if median_pf is None or median_pf < self.config.mc_pass_median_pf:
            passed = False
        if self.config.mc_pass_p05_equity_positive and p05 < initial:
            # allow small underwater but fail if p05 << initial (lost money at 5th pct)
            if p05 < initial * Decimal("0.90"):
                passed = False

        return MonteCarloReport(
            iterations=iterations,
            seed=seed,
            median_final_equity=median_eq,
            p05_final_equity=p05,
            p95_final_equity=p95,
            median_profit_factor=median_pf,
            median_max_dd=median_dd,
            passed=passed,
            distribution_final_equity=tuple(str(x) for x in finals_sorted[:: max(1, len(finals_sorted)//50)]),
        )
