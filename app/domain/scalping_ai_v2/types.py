"""Shared types for Scalping AI V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str
    score: Decimal | None
    passed: bool | None
    recommendation: str
    reasons: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "status": self.status,
            "score": str(self.score) if self.score is not None else None,
            "passed": self.passed,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "details": dict(self.details),
            "explainable": True,
            "invented": False,
            "never_order_send": True,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class ScalpCycleInput:
    """Supplied facts only — never invents market data."""

    side: str = "buy"
    # Market
    bid: Decimal | None = None
    ask: Decimal | None = None
    spread: Decimal | None = None
    atr: Decimal | None = None
    price: Decimal | None = None
    regime: str | None = None
    session: str | None = None
    trend: str | None = None
    volatility: str | None = None
    liquidity_state: str | None = None
    market_health: str | None = None
    confidence: Decimal | None = None
    # Multi-timeframe
    htf_bias: str | None = None
    ltf_confirmation: str | None = None
    trend_strength: Decimal | None = None
    trend_consistency: Decimal | None = None
    # Liquidity
    sweep_detected: bool | None = None
    equal_highs_lows: bool | None = None
    session_liquidity: str | None = None
    liquidity_side: str | None = None  # internal | external
    stop_hunt: bool | None = None
    # Structure
    bos: bool | None = None
    choch: bool | None = None
    mss: bool | None = None
    swing_bias: str | None = None
    structure_phase: str | None = None  # continuation | reversal
    # Opportunity candidates (supplied)
    opportunities: list[dict[str, Any]] | None = None
    # Authority — existing engines
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    decision_center: dict[str, Any] | None = None
    decision_approved: bool | None = None
    # Execution readiness facts
    broker_connected: bool | None = None
    gateway_healthy: bool | None = None
    latency_ms: Decimal | None = None
    market_open: bool | None = None
    margin_available: bool | None = None
    max_latency_ms: Decimal | None = None
    # Risk context
    equity: Decimal | None = None
    daily_loss_pct: Decimal | None = None
    open_exposure_pct: Decimal | None = None
    trades_today: int | None = None
    consecutive_losses: int | None = None
    # Active trade
    active_trade: dict[str, Any] | None = None
    # Closed trade for post-trade
    closed_trade: dict[str, Any] | None = None
    # Health probes for watchdog
    health: dict[str, Any] | None = None
    # Controller
    run_state: str | None = None  # running | paused | stopped | safe_mode
    kill_switch: bool | None = None
    news_blackout: bool | None = None
    technique: str | None = None
    execution_identity: str | None = None
