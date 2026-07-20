"""Phase E research configuration — separate from A-D configs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    symbol: str = GOLD_SYMBOL
    config_version: str = "ite-research-v1.0.0"
    strategy_version: str = "ite-v1.0.0"

    initial_balance: Decimal = Decimal("10000")
    contract_size: Decimal = Decimal("100")  # XAU
    default_spread: Decimal = Decimal("0.30")
    default_slippage: Decimal = Decimal("0.05")
    fill_model: str = "next_bar_open"  # approved ITE sim fill

    # Promotion (Canary) — Phase E Module 10
    promotion_min_trades: int = 300
    promotion_min_profit_factor: Decimal = Decimal("1.50")
    promotion_max_drawdown_pct: Decimal = Decimal("10")
    promotion_require_positive_expectancy: bool = True
    promotion_require_walk_forward_pass: bool = True
    promotion_require_monte_carlo_pass: bool = True

    # Monte Carlo pass thresholds
    mc_pass_median_pf: Decimal = Decimal("1.20")
    mc_pass_p05_equity_positive: bool = True

    # Walk-forward
    wf_min_oos_profit_factor: Decimal = Decimal("1.20")
    wf_min_folds_pass_ratio: Decimal = Decimal("0.60")

    optimization_top_n: int = 20

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "config_version": self.config_version,
            "strategy_version": self.strategy_version,
            "initial_balance": str(self.initial_balance),
            "fill_model": self.fill_model,
            "promotion_min_trades": self.promotion_min_trades,
            "promotion_min_profit_factor": str(self.promotion_min_profit_factor),
            "promotion_max_drawdown_pct": str(self.promotion_max_drawdown_pct),
        }


DEFAULT_RESEARCH_CONFIG = ResearchConfig()

HORIZON_MONTHS: dict[str, int] = {
    "1m": 1,
    "3m": 3,
    "6m": 6,
    "1y": 12,
    "2y": 24,
    "5y": 60,
}

REPLAY_SPEEDS: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 100.0)
