"""Real Market Intelligence Platform — read-only context config."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class RmipConfig:
    version: str = "rmip-v1.0.0"
    symbol: str = GOLD_SYMBOL
    max_archive: int = 300
    max_timeline: int = 100
    # Hard locks — context only
    allow_order_send: bool = False
    allow_place_trades: bool = False
    allow_modify_trading_rules: bool = False
    allow_modify_auto_trading: bool = False
    allow_modify_execution: bool = False
    allow_modify_decision_engine: bool = False
    allow_modify_risk_engine: bool = False
    allow_modify_safety_engine: bool = False
    invent_macro_data: bool = False
    invent_market_data: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "economic_calendar": True,
            "session_intelligence": True,
            "volatility_observatory": True,
            "liquidity_observatory": True,
            "market_context_timeline": True,
            "context_scoring": True,
            "operator_intelligence_feed": True,
            "explainability": True,
            "historical_context_archive": True,
            "context_api": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_place_trades = False
        self.allow_modify_trading_rules = False
        self.allow_modify_auto_trading = False
        self.allow_modify_execution = False
        self.allow_modify_decision_engine = False
        self.allow_modify_risk_engine = False
        self.allow_modify_safety_engine = False
        self.invent_macro_data = False
        self.invent_market_data = False

    def update(self, updates: dict[str, object]) -> RmipConfig:
        locked = {
            "allow_order_send",
            "allow_place_trades",
            "allow_modify_trading_rules",
            "allow_modify_auto_trading",
            "allow_modify_execution",
            "allow_modify_decision_engine",
            "allow_modify_risk_engine",
            "allow_modify_safety_engine",
            "invent_macro_data",
            "invent_market_data",
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
        return RmipConfig(
            max_archive=int(data["max_archive"]),
            max_timeline=int(data["max_timeline"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "max_archive": self.max_archive,
            "max_timeline": self.max_timeline,
            "allow_order_send": False,
            "allow_place_trades": False,
            "allow_modify_trading_rules": False,
            "allow_modify_auto_trading": False,
            "allow_modify_execution": False,
            "allow_modify_decision_engine": False,
            "allow_modify_risk_engine": False,
            "allow_modify_safety_engine": False,
            "invent_macro_data": False,
            "invent_market_data": False,
            "feature_flags": dict(self.feature_flags),
            "read_only": True,
            "context_only": True,
        }


DEFAULT_RMIP_CONFIG = RmipConfig()
