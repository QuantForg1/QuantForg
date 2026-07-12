"""Backtesting domain events — offline simulation facts only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class BacktestStarted(DomainEvent):
    """Emitted when a backtest run begins."""

    event_type: ClassVar[str] = "backtest.started"
    user_id: UUID
    backtest_id: UUID
    request_id: str
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "backtest_id": str(self.backtest_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BacktestFinished(DomainEvent):
    """Emitted when a backtest run completes or fails."""

    event_type: ClassVar[str] = "backtest.finished"
    user_id: UUID
    backtest_id: UUID
    request_id: str
    status: str
    trade_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "backtest_id": str(self.backtest_id),
                "request_id": self.request_id,
                "status": self.status,
                "trade_count": self.trade_count,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class TradeSimulated(DomainEvent):
    """Emitted when a simulated trade is opened or closed."""

    event_type: ClassVar[str] = "backtest.trade_simulated"
    user_id: UUID
    backtest_id: UUID
    trade_id: UUID
    symbol: str
    side: str
    action: str  # opened | closed

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "backtest_id": str(self.backtest_id),
                "trade_id": str(self.trade_id),
                "symbol": self.symbol,
                "side": self.side,
                "action": self.action,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MetricUpdated(DomainEvent):
    """Emitted when backtest metrics are recomputed."""

    event_type: ClassVar[str] = "backtest.metric_updated"
    user_id: UUID
    backtest_id: UUID
    total_return_pct: str
    max_drawdown_pct: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "backtest_id": str(self.backtest_id),
                "total_return_pct": self.total_return_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
            }
        )
        return payload
