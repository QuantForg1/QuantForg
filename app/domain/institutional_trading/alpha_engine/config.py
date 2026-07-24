"""Institutional Alpha Engine v5 — configurable multi-symbol desk knobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


DEFAULT_ALPHA_UNIVERSE: tuple[str, ...] = (
    "XAUUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "NAS100",
    "US30",
    "BTCUSD",
)

# Highly correlated pairs — never hold both when protection is on.
DEFAULT_CORRELATION_GROUPS: tuple[tuple[str, ...], ...] = (
    ("EURUSD", "GBPUSD"),
    ("NAS100", "US30"),
    ("XAUUSD", "BTCUSD"),  # risk-on soft correlation (configurable)
)


@dataclass(frozen=True, slots=True)
class InstitutionalAlphaConfig:
    """All Alpha Engine knobs — nothing hardcoded at call sites."""

    version: str = "institutional-alpha-v5.0.0"
    enabled: bool = False
    universe: tuple[str, ...] = DEFAULT_ALPHA_UNIVERSE

    # Ranking weights (sum need not be 100; normalized at score time)
    w_confidence: int = 22
    w_trend: int = 14
    w_momentum: int = 12
    w_liquidity: int = 10
    w_volatility: int = 8
    w_spread: int = 10
    w_expected_rr: int = 12
    w_session: int = 12

    min_opportunity_score: int = 72
    execute_top_n: int = 1

    # Correlation
    correlation_protection: bool = True
    correlation_groups: tuple[tuple[str, ...], ...] = DEFAULT_CORRELATION_GROUPS
    max_correlated_open: int = 1

    # Dynamic risk by opportunity quality bands
    risk_pct_high: Decimal = Decimal("1.00")  # score >= 85
    risk_pct_mid: Decimal = Decimal("0.75")  # score >= 78
    risk_pct_low: Decimal = Decimal("0.50")  # score >= min
    high_score_floor: int = 85
    mid_score_floor: int = 78
    max_daily_risk_pct: Decimal = Decimal("3.00")
    max_account_exposure_pct: Decimal = Decimal("6.00")
    max_drawdown_pct: Decimal = Decimal("8.00")

    # AI position management
    manage_interval_seconds: float = 5.0
    confidence_drop_exit: int = 18  # exit if confidence falls by this vs entry
    confidence_drop_reduce: int = 10  # partial if falls by this
    reduce_pct: Decimal = Decimal("50")
    let_profits_run_min_confidence: int = 70
    tighten_trail_confidence: int = 60
    trail_atr_mult_strong: Decimal = Decimal("1.5")
    trail_atr_mult_weak: Decimal = Decimal("0.75")

    # Smart recovery after loss
    recovery_enabled: bool = True
    recovery_risk_mult: Decimal = Decimal("0.50")
    recovery_min_score_bonus: int = 8
    recovery_trades: int = 2  # trades under recovery mode after a loss

    # Analytics
    analytics_max_records: int = 5000

    # Never allow unsafe modes
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_average_down: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "allow_martingale", False)
        object.__setattr__(self, "allow_grid", False)
        object.__setattr__(self, "allow_average_down", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "enabled": self.enabled,
            "universe": list(self.universe),
            "min_opportunity_score": self.min_opportunity_score,
            "execute_top_n": self.execute_top_n,
            "correlation_protection": self.correlation_protection,
            "correlation_groups": [list(g) for g in self.correlation_groups],
            "max_correlated_open": self.max_correlated_open,
            "risk_pct_high": str(self.risk_pct_high),
            "risk_pct_mid": str(self.risk_pct_mid),
            "risk_pct_low": str(self.risk_pct_low),
            "max_daily_risk_pct": str(self.max_daily_risk_pct),
            "max_account_exposure_pct": str(self.max_account_exposure_pct),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "manage_interval_seconds": self.manage_interval_seconds,
            "confidence_drop_exit": self.confidence_drop_exit,
            "confidence_drop_reduce": self.confidence_drop_reduce,
            "let_profits_run_min_confidence": self.let_profits_run_min_confidence,
            "tighten_trail_confidence": self.tighten_trail_confidence,
            "recovery_enabled": self.recovery_enabled,
            "recovery_risk_mult": str(self.recovery_risk_mult),
            "recovery_min_score_bonus": self.recovery_min_score_bonus,
            "recovery_trades": self.recovery_trades,
            "allow_martingale": self.allow_martingale,
            "allow_grid": self.allow_grid,
            "allow_average_down": self.allow_average_down,
            "weights": {
                "confidence": self.w_confidence,
                "trend": self.w_trend,
                "momentum": self.w_momentum,
                "liquidity": self.w_liquidity,
                "volatility": self.w_volatility,
                "spread": self.w_spread,
                "expected_rr": self.w_expected_rr,
                "session": self.w_session,
            },
        }


DEFAULT_ALPHA_CONFIG = InstitutionalAlphaConfig()
