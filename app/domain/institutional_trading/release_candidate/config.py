"""Release Candidate RC1 — production readiness config (validation only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReleaseCandidateConfig:
    version: str = "release-candidate-rc1.0.0"

    # Hard locks — validation / evidence only
    smoke_never_places_orders: bool = True
    never_auto_scale_capital: bool = True
    never_mix_trading_venues: bool = True
    no_new_strategies: bool = True
    no_experimental_production_logic: bool = True

    # Go Live Score — recommend scale-up only above threshold
    go_live_score_threshold: float = 80.0
    min_consecutive_trading_days: int = 14
    recommended_evidence_days: int = 28

    # Capital advisor defaults (recommendations only)
    capital_scale_factor: float = 2.5
    max_suggested_scale_factor: float = 3.0
    max_drawdown_pct_for_scale: float = 8.0
    min_win_rate_for_scale: float = 50.0
    min_sharpe_for_scale: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "smoke_never_places_orders": True,
            "never_auto_scale_capital": True,
            "never_mix_trading_venues": True,
            "no_new_strategies": True,
            "no_experimental_production_logic": True,
            "go_live_score_threshold": self.go_live_score_threshold,
            "min_consecutive_trading_days": self.min_consecutive_trading_days,
            "recommended_evidence_days": self.recommended_evidence_days,
            "note": (
                "RC1 proves profitability, stability, and safety with measurable evidence. "
                "Never auto-scale capital. Never place real trades in smoke tests."
            ),
        }


DEFAULT_RC1_CONFIG = ReleaseCandidateConfig()

CHECKLIST_ITEMS = (
    "mt5_gateway",
    "broker",
    "oms",
    "ai_engine",
    "portfolio_engine",
    "position_recovery",
    "health_monitoring",
    "retry_engine",
    "dashboard",
    "railway_environment",
    "secrets",
    "database",
    "market_data",
)

SMOKE_CHECKS = (
    "gateway_connectivity",
    "broker_login",
    "symbol_availability",
    "margin_retrieval",
    "spread_retrieval",
    "order_validation",
    "position_sync",
)

TRADING_VENUES = ("paper", "demo", "live")
CheckStatus = str  # PASS | WARNING | FAIL
