"""Institutional Edge Engine — config (XAUUSD, advisory-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class IeeConfig:
    version: str = "iee-v1.0.0"
    symbol: str = GOLD_SYMBOL
    min_trades_for_edge: int = 20
    min_trades_for_regime: int = 8
    min_trades_for_entry_exit: int = 10
    rolling_windows: tuple[int, ...] = (50, 100, 250)
    edge_warning_threshold: Decimal = Decimal("45")
    edge_critical_threshold: Decimal = Decimal("30")
    stability_variance_warn: Decimal = Decimal("25")
    max_history: int = 200
    # Hard locks
    allow_order_send: bool = False
    allow_disable_trading: bool = False
    allow_modify_strategy_rules: bool = False
    allow_modify_risk_policies: bool = False
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_bypass_decision: bool = False
    invent_metrics: bool = False
    promise_profitability: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "edge_scoring": True,
            "strategy_stability": True,
            "regime_performance": True,
            "entry_quality": True,
            "exit_quality": True,
            "risk_discipline": True,
            "edge_decay": True,
            "explainable_edge_report": True,
            "institutional_scorecard": True,
            "monthly_research_package": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_disable_trading = False
        self.allow_modify_strategy_rules = False
        self.allow_modify_risk_policies = False
        self.allow_bypass_risk = False
        self.allow_bypass_safety = False
        self.allow_bypass_decision = False
        self.invent_metrics = False
        self.promise_profitability = False

    def update(self, updates: dict[str, object]) -> IeeConfig:
        locked = {
            "allow_order_send",
            "allow_disable_trading",
            "allow_modify_strategy_rules",
            "allow_modify_risk_policies",
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_bypass_decision",
            "invent_metrics",
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
            elif key == "rolling_windows" and isinstance(value, (list, tuple)):
                data["rolling_windows"] = [int(x) for x in value]
            elif key in data:
                data[key] = value
        return IeeConfig(
            min_trades_for_edge=int(data["min_trades_for_edge"]),
            min_trades_for_regime=int(data["min_trades_for_regime"]),
            min_trades_for_entry_exit=int(data["min_trades_for_entry_exit"]),
            rolling_windows=tuple(data["rolling_windows"]),  # type: ignore[arg-type]
            edge_warning_threshold=Decimal(str(data["edge_warning_threshold"])),
            edge_critical_threshold=Decimal(
                str(data["edge_critical_threshold"])
            ),
            stability_variance_warn=Decimal(
                str(data["stability_variance_warn"])
            ),
            max_history=int(data["max_history"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_trades_for_edge": self.min_trades_for_edge,
            "min_trades_for_regime": self.min_trades_for_regime,
            "min_trades_for_entry_exit": self.min_trades_for_entry_exit,
            "rolling_windows": list(self.rolling_windows),
            "edge_warning_threshold": str(self.edge_warning_threshold),
            "edge_critical_threshold": str(self.edge_critical_threshold),
            "stability_variance_warn": str(self.stability_variance_warn),
            "max_history": self.max_history,
            "allow_order_send": False,
            "allow_disable_trading": False,
            "allow_modify_strategy_rules": False,
            "allow_modify_risk_policies": False,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_bypass_decision": False,
            "invent_metrics": False,
            "promise_profitability": False,
            "feature_flags": dict(self.feature_flags),
        }


DEFAULT_IEE_CONFIG = IeeConfig()
