"""Institutional Portfolio Intelligence v9 — config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PortfolioIntelligenceConfig:
    version: str = "portfolio-intelligence-v9.0.0"

    # Dynamic risk budget (never martingale/grid)
    base_risk_budget_pct: float = 4.0
    min_risk_budget_pct: float = 1.0
    max_risk_budget_pct: float = 6.0
    strong_performance_days: int = 5
    budget_step_up: float = 0.25
    budget_step_down: float = 0.5
    drawdown_cut_pct: float = 3.0

    # Capital protection ceilings
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 6.0
    max_monthly_loss_pct: float = 12.0
    max_symbol_exposure_pct: float = 40.0
    max_correlated_exposure_pct: float = 50.0
    max_session_exposure_pct: float = 60.0
    max_leverage: float = 10.0

    # Soft approach thresholds (reduce new exposure before hard stop)
    approach_ratio: float = 0.75

    # Allocation shares for ranked opportunities (dynamic, not fixed rules —
    # these are *starting* weights scaled by scores/correlation)
    reserve_floor: float = 0.10

    # Recommendations never auto-apply
    recommendations_auto_apply: bool = False
    capital_reallocation_auto: bool = False

    max_queue: int = 50
    max_explanations: int = 2_000
    max_recommendations: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "base_risk_budget_pct": self.base_risk_budget_pct,
            "min_risk_budget_pct": self.min_risk_budget_pct,
            "max_risk_budget_pct": self.max_risk_budget_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_monthly_loss_pct": self.max_monthly_loss_pct,
            "recommendations_auto_apply": False,
            "capital_reallocation_auto": False,
            "martingale": False,
            "grid": False,
            "note": "Advisory portfolio intelligence — no automatic capital reallocation",
        }


DEFAULT_PI_CONFIG = PortfolioIntelligenceConfig()
