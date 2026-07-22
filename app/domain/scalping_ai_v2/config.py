"""Institutional XAUUSD Scalping AI V2 — configurable production knobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import MAX_SPREAD, coerce_max_spread


@dataclass
class ScalpingAiV2Config:
    """Configuration Center — every production knob is configurable."""

    version: str = "scalping-ai-v2.1.0"
    symbol: str = GOLD_SYMBOL
    # Market quality
    min_market_quality: Decimal = Decimal("60")
    min_confidence: Decimal = Decimal("65")
    max_spread: Decimal = MAX_SPREAD
    min_atr_pct: Decimal = Decimal("0.05")
    max_atr_pct: Decimal = Decimal("3.0")
    allowed_sessions: tuple[str, ...] = (
        "london",
        "new_york",
        "london_ny_overlap",
        "asian",
    )
    # Opportunity ranking gates
    min_quality_score: Decimal = Decimal("65")
    min_execution_score: Decimal = Decimal("60")
    max_risk_score: Decimal = Decimal("70")
    # Dynamic risk (advisory — existing Risk Engine remains authoritative)
    base_risk_pct: Decimal = Decimal("0.50")
    risk_floor_pct: Decimal = Decimal("0.15")
    max_daily_loss_pct: Decimal = Decimal("2.00")
    max_trades_per_day: int = 20
    max_open_exposure_pct: Decimal = Decimal("5.00")
    # Trade management (policy-driven advisory only)
    break_even_enabled: bool = True
    break_even_at_r: Decimal = Decimal("1.0")
    trailing_enabled: bool = True
    trail_after_r: Decimal = Decimal("1.5")
    partial_exit_enabled: bool = False
    partial_exit_at_r: Decimal = Decimal("2.0")
    partial_exit_pct: Decimal = Decimal("50")
    # Reliability
    max_retries: int = 5
    retry_backoff_ms: int = 250
    max_retry_backoff_ms: int = 30_000
    watchdog_interval_sec: int = 15
    controller_scan_interval_sec: int = 5
    # Hard locks
    allow_order_send: bool = False
    allow_bypass_risk: bool = False
    allow_bypass_safety: bool = False
    allow_bypass_decision_center: bool = False
    allow_alternate_execution_path: bool = False
    promise_profitability: bool = False
    invent_market_data: bool = False
    allow_martingale: bool = False
    allow_grid: bool = False
    allow_average_losers: bool = False
    prefer_no_trade: bool = True
    max_events: int = 5000
    max_history: int = 500
    # V2.1 hardening knobs
    retry_jitter_ratio: float = 0.2
    max_clock_drift_ms: int = 5000
    max_loop_latency_ms: int = 5000
    state_persist_enabled: bool = True
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "market_quality": True,
            "multi_timeframe": True,
            "liquidity_intelligence": True,
            "market_structure": True,
            "opportunity_ranking": True,
            "dynamic_risk": True,
            "execution_monitor": True,
            "trade_supervisor": True,
            "auto_controller": True,
            "watchdog": True,
            "incident_recovery": True,
            "duplicate_protection": True,
            "event_bus": True,
            "analytics": True,
            "post_trade": True,
            "observability": True,
            "long_running_stability": True,
            "state_persistence": True,
            "restart_recovery": True,
            "mt5_synchronization": True,
            "data_integrity": True,
            "safe_mode": True,
            "emergency_stop": True,
            "latency_monitor": True,
            "intelligent_retry": True,
            "production_diagnostics": True,
            "soak_testing": True,
            "production_audit": True,
            "operator_dashboard": True,
        }
    )

    def __post_init__(self) -> None:
        self.symbol = GOLD_SYMBOL
        self.max_spread = coerce_max_spread(self.max_spread)
        self.allow_order_send = False
        self.allow_bypass_risk = False
        self.allow_bypass_safety = False
        self.allow_bypass_decision_center = False
        self.allow_alternate_execution_path = False
        self.promise_profitability = False
        self.invent_market_data = False
        self.allow_martingale = False
        self.allow_grid = False
        self.allow_average_losers = False
        self.prefer_no_trade = True

    def update(self, updates: dict[str, object]) -> ScalpingAiV2Config:
        locked = {
            "allow_order_send",
            "allow_bypass_risk",
            "allow_bypass_safety",
            "allow_bypass_decision_center",
            "allow_alternate_execution_path",
            "promise_profitability",
            "invent_market_data",
            "allow_martingale",
            "allow_grid",
            "allow_average_losers",
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
                    if isinstance(fv, bool) and fk not in {
                        "order_send",
                        "bypass_risk",
                        "bypass_safety",
                    }:
                        flags[str(fk)] = fv
                data["feature_flags"] = flags
            elif key == "allowed_sessions" and isinstance(value, (list, tuple)):
                data["allowed_sessions"] = [str(s) for s in value]
            elif key in data:
                data[key] = value
        return ScalpingAiV2Config(
            min_market_quality=Decimal(str(data["min_market_quality"])),
            min_confidence=Decimal(str(data["min_confidence"])),
            max_spread=Decimal(str(data["max_spread"])),
            min_atr_pct=Decimal(str(data["min_atr_pct"])),
            max_atr_pct=Decimal(str(data["max_atr_pct"])),
            allowed_sessions=tuple(data["allowed_sessions"]),  # type: ignore[arg-type]
            min_quality_score=Decimal(str(data["min_quality_score"])),
            min_execution_score=Decimal(str(data["min_execution_score"])),
            max_risk_score=Decimal(str(data["max_risk_score"])),
            base_risk_pct=Decimal(str(data["base_risk_pct"])),
            risk_floor_pct=Decimal(str(data["risk_floor_pct"])),
            max_daily_loss_pct=Decimal(str(data["max_daily_loss_pct"])),
            max_trades_per_day=int(data["max_trades_per_day"]),
            max_open_exposure_pct=Decimal(str(data["max_open_exposure_pct"])),
            break_even_enabled=bool(data["break_even_enabled"]),
            break_even_at_r=Decimal(str(data["break_even_at_r"])),
            trailing_enabled=bool(data["trailing_enabled"]),
            trail_after_r=Decimal(str(data["trail_after_r"])),
            partial_exit_enabled=bool(data["partial_exit_enabled"]),
            partial_exit_at_r=Decimal(str(data["partial_exit_at_r"])),
            partial_exit_pct=Decimal(str(data["partial_exit_pct"])),
            max_retries=int(data["max_retries"]),
            retry_backoff_ms=int(data["retry_backoff_ms"]),
            max_retry_backoff_ms=int(data["max_retry_backoff_ms"]),
            watchdog_interval_sec=int(data["watchdog_interval_sec"]),
            controller_scan_interval_sec=int(
                data["controller_scan_interval_sec"]
            ),
            max_events=int(data["max_events"]),
            max_history=int(data["max_history"]),
            retry_jitter_ratio=float(data.get("retry_jitter_ratio", 0.2)),
            max_clock_drift_ms=int(data.get("max_clock_drift_ms", 5000)),
            max_loop_latency_ms=int(data.get("max_loop_latency_ms", 5000)),
            state_persist_enabled=bool(data.get("state_persist_enabled", True)),
            feature_flags=dict(data["feature_flags"]),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "min_market_quality": str(self.min_market_quality),
            "min_confidence": str(self.min_confidence),
            "max_spread": str(self.max_spread),
            "min_atr_pct": str(self.min_atr_pct),
            "max_atr_pct": str(self.max_atr_pct),
            "allowed_sessions": list(self.allowed_sessions),
            "min_quality_score": str(self.min_quality_score),
            "min_execution_score": str(self.min_execution_score),
            "max_risk_score": str(self.max_risk_score),
            "base_risk_pct": str(self.base_risk_pct),
            "risk_floor_pct": str(self.risk_floor_pct),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_trades_per_day": self.max_trades_per_day,
            "max_open_exposure_pct": str(self.max_open_exposure_pct),
            "break_even_enabled": self.break_even_enabled,
            "break_even_at_r": str(self.break_even_at_r),
            "trailing_enabled": self.trailing_enabled,
            "trail_after_r": str(self.trail_after_r),
            "partial_exit_enabled": self.partial_exit_enabled,
            "partial_exit_at_r": str(self.partial_exit_at_r),
            "partial_exit_pct": str(self.partial_exit_pct),
            "max_retries": self.max_retries,
            "retry_backoff_ms": self.retry_backoff_ms,
            "max_retry_backoff_ms": self.max_retry_backoff_ms,
            "watchdog_interval_sec": self.watchdog_interval_sec,
            "controller_scan_interval_sec": self.controller_scan_interval_sec,
            "allow_order_send": False,
            "allow_bypass_risk": False,
            "allow_bypass_safety": False,
            "allow_bypass_decision_center": False,
            "allow_alternate_execution_path": False,
            "promise_profitability": False,
            "invent_market_data": False,
            "allow_martingale": False,
            "allow_grid": False,
            "allow_average_losers": False,
            "prefer_no_trade": True,
            "max_events": self.max_events,
            "max_history": self.max_history,
            "retry_jitter_ratio": self.retry_jitter_ratio,
            "max_clock_drift_ms": self.max_clock_drift_ms,
            "max_loop_latency_ms": self.max_loop_latency_ms,
            "state_persist_enabled": self.state_persist_enabled,
            "feature_flags": dict(self.feature_flags),
        }


DEFAULT_SCALPING_CONFIG = ScalpingAiV2Config()
