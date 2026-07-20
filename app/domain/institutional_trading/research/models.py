"""Phase E research contracts — trades, analytics, simulation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID


class Horizon(StrEnum):
    M1 = "1m"
    M3 = "3m"
    M6 = "6m"
    Y1 = "1y"
    Y2 = "2y"
    Y5 = "5y"


class WalkForwardMode(StrEnum):
    ROLLING = "rolling"
    ANCHORED = "anchored"


@dataclass(frozen=True, slots=True)
class ResearchBar:
    """OHLC bar for deterministic candle replay."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    session: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
            "session": self.session,
        }


@dataclass(frozen=True, slots=True)
class EquityPoint:
    time: datetime
    equity: Decimal
    drawdown_pct: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time.isoformat(),
            "equity": str(self.equity),
            "drawdown_pct": str(self.drawdown_pct),
        }


@dataclass
class ResearchTrade:
    """Closed or open simulated trade with full decision/management trail."""

    trade_id: str
    symbol: str
    side: str
    entry_time: datetime
    entry_price: Decimal
    volume: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None = None
    exit_time: datetime | None = None
    exit_price: Decimal | None = None
    pnl: Decimal = Decimal("0")
    r_multiple: Decimal | None = None
    status: str = "open"  # open | closed
    exit_reason: str = ""
    session: str = ""
    # Decision context
    confidence: int = 0
    quality: int = 0
    risk_score: int = 0
    decision_reasons: tuple[str, ...] = ()
    confluence: dict[str, Any] = field(default_factory=dict)
    # Management events
    events: list[dict[str, Any]] = field(default_factory=list)
    mae: Decimal = Decimal("0")  # max adverse excursion (price)
    mfe: Decimal = Decimal("0")  # max favorable excursion (price)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": str(self.entry_price),
            "volume": str(self.volume),
            "stop_loss": str(self.stop_loss),
            "take_profit": str(self.take_profit) if self.take_profit else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": str(self.exit_price) if self.exit_price else None,
            "pnl": str(self.pnl),
            "r_multiple": str(self.r_multiple) if self.r_multiple is not None else None,
            "status": self.status,
            "exit_reason": self.exit_reason,
            "session": self.session,
            "confidence": self.confidence,
            "quality": self.quality,
            "risk_score": self.risk_score,
            "decision_reasons": list(self.decision_reasons),
            "confluence": dict(self.confluence),
            "events": list(self.events),
            "mae": str(self.mae),
            "mfe": str(self.mfe),
        }


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    """Full institutional analytics schema."""

    win_rate: Decimal
    expectancy: Decimal
    profit_factor: Decimal | None
    average_rr: Decimal | None
    max_drawdown_pct: Decimal
    sharpe: Decimal | None
    sortino: Decimal | None
    calmar: Decimal | None
    recovery_factor: Decimal | None
    average_hold_seconds: float
    best_session: str
    worst_session: str
    longest_win_streak: int
    longest_loss_streak: int
    mae_avg: Decimal
    mfe_avg: Decimal
    trade_count: int
    win_count: int
    loss_count: int
    total_return_pct: Decimal
    monthly_returns: dict[str, str] = field(default_factory=dict)
    equity_curve: tuple[EquityPoint, ...] = ()
    pnl_distribution: tuple[str, ...] = ()
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "win_rate": str(self.win_rate),
            "expectancy": str(self.expectancy),
            "profit_factor": (
                str(self.profit_factor) if self.profit_factor is not None else None
            ),
            "average_rr": str(self.average_rr) if self.average_rr is not None else None,
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "sharpe": str(self.sharpe) if self.sharpe is not None else None,
            "sortino": str(self.sortino) if self.sortino is not None else None,
            "calmar": str(self.calmar) if self.calmar is not None else None,
            "recovery_factor": (
                str(self.recovery_factor) if self.recovery_factor is not None else None
            ),
            "average_hold_seconds": self.average_hold_seconds,
            "best_session": self.best_session,
            "worst_session": self.worst_session,
            "longest_win_streak": self.longest_win_streak,
            "longest_loss_streak": self.longest_loss_streak,
            "mae_avg": str(self.mae_avg),
            "mfe_avg": str(self.mfe_avg),
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "total_return_pct": str(self.total_return_pct),
            "monthly_returns": dict(self.monthly_returns),
            "equity_curve": [p.to_dict() for p in self.equity_curve],
            "pnl_distribution": list(self.pnl_distribution),
        }


@dataclass(frozen=True, slots=True)
class SimulationResult:
    run_id: UUID
    trades: tuple[ResearchTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    analytics: AnalyticsReport
    input_hash: str
    strategy_version: str
    config_version: str
    git_commit: str | None
    bars_processed: int
    deterministic: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [e.to_dict() for e in self.equity_curve],
            "analytics": self.analytics.to_dict(),
            "input_hash": self.input_hash,
            "strategy_version": self.strategy_version,
            "config_version": self.config_version,
            "git_commit": self.git_commit,
            "bars_processed": self.bars_processed,
            "deterministic": self.deterministic,
        }


@dataclass(frozen=True, slots=True)
class PromotionReport:
    eligible: bool
    target: str  # canary
    checks: dict[str, bool]
    reasons: tuple[str, ...]
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "target": self.target,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
            "metrics_snapshot": dict(self.metrics_snapshot),
        }
