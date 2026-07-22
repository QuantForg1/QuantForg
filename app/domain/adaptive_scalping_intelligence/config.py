"""Adaptive Scalping Intelligence — config (XAUUSD, advisory-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class AsiConfig:
    version: str = "asi-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_history_observations: int = 20
    min_session_samples: int = 5
    min_pattern_samples: int = 8
    min_calibration_samples: int = 15
    heat_map_buckets: int = 6
    coach_lookback_days: int = 7
    max_history: int = 300
    max_opportunity_db: int = 500
    # Hard locks
    allow_order_send: bool = False
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_bypass_decision: bool = False
    allow_modify_trading_rules: bool = False
    allow_modify_risk_policies: bool = False
    invent_statistics: bool = False
    promise_profitability: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "market_personality": True,
            "session_intelligence": True,
            "time_intelligence": True,
            "opportunity_database": True,
            "pattern_intelligence": True,
            "confidence_calibration": True,
            "opportunity_heat_map": True,
            "capital_preservation_index": True,
            "decision_explainability": True,
            "weekly_ai_coach": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_bypass_risk = False
        self.allow_bypass_safety = False
        self.allow_bypass_decision = False
        self.allow_modify_trading_rules = False
        self.allow_modify_risk_policies = False
        self.invent_statistics = False
        self.promise_profitability = False

    def update(self, updates: dict[str, object]) -> AsiConfig:
        locked = {
            "allow_order_send",
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_bypass_decision",
            "allow_modify_trading_rules",
            "allow_modify_risk_policies",
            "invent_statistics",
            "promise_profitability",
            "symbol",
            "version",
        }
        data = self.to_dict()
        for key, value in updates.items():
            if key in locked or value is None:
                continue
            if key == "feature_flags" and isinstance(value, dict):
                flags = dict(data["feature_flags"])  # type: ignore[arg-type]
                for fk, fv in value.items():
                    if isinstance(fv, bool):
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return AsiConfig(
            min_history_observations=int(data["min_history_observations"]),
            min_session_samples=int(data["min_session_samples"]),
            min_pattern_samples=int(data["min_pattern_samples"]),
            min_calibration_samples=int(data["min_calibration_samples"]),
            heat_map_buckets=int(data["heat_map_buckets"]),
            coach_lookback_days=int(data["coach_lookback_days"]),
            max_history=int(data["max_history"]),
            max_opportunity_db=int(data["max_opportunity_db"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_history_observations": self.min_history_observations,
            "min_session_samples": self.min_session_samples,
            "min_pattern_samples": self.min_pattern_samples,
            "min_calibration_samples": self.min_calibration_samples,
            "heat_map_buckets": self.heat_map_buckets,
            "coach_lookback_days": self.coach_lookback_days,
            "max_history": self.max_history,
            "max_opportunity_db": self.max_opportunity_db,
            "allow_order_send": False,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_bypass_decision": False,
            "allow_modify_trading_rules": False,
            "allow_modify_risk_policies": False,
            "invent_statistics": False,
            "promise_profitability": False,
            "feature_flags": dict(self.feature_flags),
            "min_composite_hint": str(Decimal("60")),
        }


DEFAULT_ASI_CONFIG = AsiConfig()
