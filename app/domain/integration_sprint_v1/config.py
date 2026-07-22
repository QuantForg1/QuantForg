"""Integration Sprint V1 — read-only feed config."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.trading.gold_only import GOLD_SYMBOL

MISSING = "MISSING DATA"
FEED_NAMES = (
    "mt5_trade_feed",
    "mt5_position_feed",
    "mt5_market_data_feed",
    "broker_account_feed",
    "execution_journal_feed",
    "analytics_feed",
    "historical_data_warehouse",
    "economic_calendar_provider",
    "durable_storage",
    "unified_data_bus",
)


@dataclass
class IntegrationSprintConfig:
    version: str = "integration-sprint-v1.0.0"
    symbol: str = GOLD_SYMBOL
    max_deals: int = 200
    max_journal: int = 200
    max_calendar_events: int = 50
    max_warehouse_bars: int = 500
    max_durable_per_namespace: int = 2_000
    stale_after_seconds: float = 120.0
    # Hard locks
    allow_order_send: bool = False
    allow_modify_auto_trading: bool = False
    allow_modify_execution_pipeline: bool = False
    allow_modify_decision_engine: bool = False
    allow_modify_risk_engine: bool = False
    allow_modify_safety_engine: bool = False
    invent_market_data: bool = False
    invent_trades: bool = False
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: dict.fromkeys(FEED_NAMES, True)
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.allow_order_send = False
        self.allow_modify_auto_trading = False
        self.allow_modify_execution_pipeline = False
        self.allow_modify_decision_engine = False
        self.allow_modify_risk_engine = False
        self.allow_modify_safety_engine = False
        self.invent_market_data = False
        self.invent_trades = False

    def update(self, updates: dict[str, object]) -> IntegrationSprintConfig:
        locked = {
            "allow_order_send",
            "allow_modify_auto_trading",
            "allow_modify_execution_pipeline",
            "allow_modify_decision_engine",
            "allow_modify_risk_engine",
            "allow_modify_safety_engine",
            "invent_market_data",
            "invent_trades",
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
                    if isinstance(fv, bool) and str(fk) in FEED_NAMES:
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key in data:
                data[key] = value
        return IntegrationSprintConfig(
            max_deals=int(data["max_deals"]),
            max_journal=int(data["max_journal"]),
            max_calendar_events=int(data["max_calendar_events"]),
            max_warehouse_bars=int(data["max_warehouse_bars"]),
            max_durable_per_namespace=int(data["max_durable_per_namespace"]),
            stale_after_seconds=float(data["stale_after_seconds"]),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "max_deals": self.max_deals,
            "max_journal": self.max_journal,
            "max_calendar_events": self.max_calendar_events,
            "max_warehouse_bars": self.max_warehouse_bars,
            "max_durable_per_namespace": self.max_durable_per_namespace,
            "stale_after_seconds": self.stale_after_seconds,
            "allow_order_send": False,
            "allow_modify_auto_trading": False,
            "allow_modify_execution_pipeline": False,
            "allow_modify_decision_engine": False,
            "allow_modify_risk_engine": False,
            "allow_modify_safety_engine": False,
            "invent_market_data": False,
            "invent_trades": False,
            "feature_flags": dict(self.feature_flags),
            "read_only": True,
            "feeds": list(FEED_NAMES),
        }


DEFAULT_INTEGRATION_CONFIG = IntegrationSprintConfig()
