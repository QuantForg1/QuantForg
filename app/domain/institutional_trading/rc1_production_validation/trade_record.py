"""Eligible / rejected trade journal records for RC1 validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class TradeRecord:
    """One eligible or rejected trade evidence row — never fabricates fills."""

    trade_id: str = field(default_factory=lambda: f"trd_{uuid4().hex[:16]}")
    timestamp: str = field(default_factory=_now_iso)
    symbol: str = ""
    market_regime: str = ""
    session: str = ""
    quality: int | None = None
    confidence: int | None = None
    risk_profile: str = ""
    entry: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    risk_reward: str | None = None
    expected_lot_size: str | None = None
    portfolio_allocation: str | None = None
    reason_accepted: str = ""
    reason_rejected: str = ""
    accepted: bool = False
    oms_latency_ms: float | None = None
    ai_latency_ms: float | None = None
    gateway_latency_ms: float | None = None
    execution_mode: str = ""
    order_payload: dict[str, Any] = field(default_factory=dict)
    broker_request: dict[str, Any] = field(default_factory=dict)
    broker_response: dict[str, Any] = field(default_factory=dict)
    expected_execution: dict[str, Any] = field(default_factory=dict)
    fill: dict[str, Any] = field(default_factory=dict)
    pnl: str | None = None
    notes: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "market_regime": self.market_regime,
            "session": self.session,
            "quality": self.quality,
            "confidence": self.confidence,
            "risk_profile": self.risk_profile,
            "entry": self.entry,
            "SL": self.stop_loss,
            "TP": self.take_profit,
            "RR": self.risk_reward,
            "expected_lot_size": self.expected_lot_size,
            "portfolio_allocation": self.portfolio_allocation,
            "reason_accepted": self.reason_accepted,
            "reason_rejected": self.reason_rejected,
            "accepted": self.accepted,
            "OMS_latency_ms": self.oms_latency_ms,
            "AI_latency_ms": self.ai_latency_ms,
            "gateway_latency_ms": self.gateway_latency_ms,
            "execution_mode": self.execution_mode,
            "order_payload": dict(self.order_payload),
            "broker_request": dict(self.broker_request),
            "broker_response": dict(self.broker_response),
            "expected_execution": dict(self.expected_execution),
            "fill": dict(self.fill),
            "pnl": self.pnl,
            "notes": self.notes,
            "extras": dict(self.extras),
        }
