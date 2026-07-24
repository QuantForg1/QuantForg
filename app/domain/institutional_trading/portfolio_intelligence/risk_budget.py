"""Dynamic risk budget — adaptive, never martingale/grid."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
    PortfolioIntelligenceConfig,
)
from app.domain.institutional_trading.portfolio_intelligence.state import PortfolioState


@dataclass
class DynamicRiskBudget:
    current_pct: float = DEFAULT_PI_CONFIG.base_risk_budget_pct
    strong_streak: int = 0
    weak_streak: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def observe_day(self, *, positive: bool, config: PortfolioIntelligenceConfig | None = None) -> None:
        cfg = config or DEFAULT_PI_CONFIG
        with self._lock:
            if positive:
                self.strong_streak += 1
                self.weak_streak = 0
                if self.strong_streak >= cfg.strong_performance_days:
                    self.current_pct = min(
                        cfg.max_risk_budget_pct,
                        self.current_pct + cfg.budget_step_up,
                    )
                    self.strong_streak = 0
            else:
                self.weak_streak += 1
                self.strong_streak = 0

    def budget_for_state(
        self,
        state: PortfolioState,
        *,
        config: PortfolioIntelligenceConfig | None = None,
    ) -> dict[str, Any]:
        cfg = config or DEFAULT_PI_CONFIG
        with self._lock:
            pct = self.current_pct
        reason = "base/adaptive budget"
        if state.current_drawdown_pct >= cfg.drawdown_cut_pct:
            pct = max(cfg.min_risk_budget_pct, pct - cfg.budget_step_down)
            reason = f"drawdown {state.current_drawdown_pct}% → reduced budget"
        if state.daily_pnl < 0 and state.equity > 0:
            daily_loss_pct = abs(state.daily_pnl) / state.equity * 100.0
            if daily_loss_pct >= cfg.max_daily_loss_pct * cfg.approach_ratio:
                pct = max(cfg.min_risk_budget_pct, pct * 0.7)
                reason = "approaching daily loss limit"
        pct = max(cfg.min_risk_budget_pct, min(cfg.max_risk_budget_pct, pct))
        return {
            "risk_budget_pct": round(pct, 3),
            "reason": reason,
            "martingale": False,
            "grid": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "current_pct": self.current_pct,
                "strong_streak": self.strong_streak,
                "weak_streak": self.weak_streak,
            }


_BUDGET: DynamicRiskBudget | None = None
_LOCK = threading.Lock()


def get_dynamic_risk_budget() -> DynamicRiskBudget:
    global _BUDGET
    with _LOCK:
        if _BUDGET is None:
            _BUDGET = DynamicRiskBudget()
        return _BUDGET
