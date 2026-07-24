"""AI Validation & Performance Optimization v7 — config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AiValidationConfig:
    version: str = "ai-validation-v7.0.0"

    shadow_enabled: bool = True
    # Never override primary by default — log disagreements only
    shadow_veto_enabled: bool = False
    shadow_confidence_delta: int = 15
    shadow_rr_delta: float = 0.35
    shadow_risk_delta: int = 20

    # Weight optimizer — gradual only; never changes trading rules
    optimizer_enabled: bool = True
    optimizer_step: float = 0.015
    optimizer_min: float = 0.5
    optimizer_max: float = 1.5

    # Alerts — observational; do not halt trading here
    alert_win_rate_floor: float = 35.0
    alert_drawdown_pct: float = 8.0
    alert_slippage_spike: float = 2.0
    alert_latency_spike_ms: float = 3_000.0
    alert_consecutive_losses: int = 5

    # Stores
    max_shadow_comparisons: int = 5_000
    max_opportunity_days: int = 90
    max_optimization_logs: int = 2_000
    max_alerts: int = 500

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "shadow_enabled": self.shadow_enabled,
            "shadow_veto_enabled": self.shadow_veto_enabled,
            "shadow_confidence_delta": self.shadow_confidence_delta,
            "shadow_rr_delta": self.shadow_rr_delta,
            "optimizer_enabled": self.optimizer_enabled,
            "optimizer_step": self.optimizer_step,
            "alert_win_rate_floor": self.alert_win_rate_floor,
            "alert_drawdown_pct": self.alert_drawdown_pct,
            "alert_slippage_spike": self.alert_slippage_spike,
            "alert_latency_spike_ms": self.alert_latency_spike_ms,
            "alert_consecutive_losses": self.alert_consecutive_losses,
        }


DEFAULT_AI_VALIDATION_CONFIG = AiValidationConfig()

OPTIMIZER_FACTORS: tuple[str, ...] = (
    "trend",
    "liquidity",
    "momentum",
    "volatility",
    "session",
    "bos",
    "choch",
    "fvg",
    "order_block",
)

STRATEGIES: tuple[str, ...] = ("scalping", "intraday", "swing")
