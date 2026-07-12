"""Backtesting domain models — offline simulation only, never live broker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.backtest import (
    BacktestStatus,
    ReplayControlState,
    ReplayMode,
    SimulatedExitReason,
    SimulatedTradeSide,
    SimulatedTradeStatus,
)


@dataclass(frozen=True, slots=True)
class BacktestAssumptions:
    """Cost and fill assumptions for simulated trades (not live quotes)."""

    spread: Decimal = Decimal("0.00010")
    slippage: Decimal = Decimal("0.00005")
    fee_per_lot: Decimal = Decimal("7")
    lot_size: Decimal = Decimal("0.10")
    stop_loss_distance: Decimal = Decimal("0.0020")
    take_profit_distance: Decimal = Decimal("0.0040")
    contract_size: Decimal = Decimal("100000")
    leverage: int = 100

    def __post_init__(self) -> None:
        require(self.spread >= 0, "spread must be >= 0")
        require(self.slippage >= 0, "slippage must be >= 0")
        require(self.fee_per_lot >= 0, "fee_per_lot must be >= 0")
        require(self.lot_size > 0, "lot_size must be > 0")
        require(self.contract_size > 0, "contract_size must be > 0")
        require(self.leverage > 0, "leverage must be > 0")


@dataclass
class VirtualClock:
    """Deterministic virtual clock for historical replay."""

    current: datetime
    speed: float = 1.0  # 1.0 = real-time ratio (informational for step mode)
    _paused: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.current.tzinfo is None:
            self.current = self.current.replace(tzinfo=UTC)
        require(self.speed > 0, "speed must be > 0")

    @property
    def paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def set_speed(self, speed: float) -> None:
        require(speed > 0, "speed must be > 0")
        self.speed = speed

    def advance_to(self, moment: datetime) -> None:
        if self._paused:
            return
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        self.current = moment

    def step(self, delta: timedelta) -> datetime:
        if self._paused:
            return self.current
        self.current = self.current + delta
        return self.current


@dataclass
class ReplayController:
    """Controls candle/tick replay: pause, resume, step, speed."""

    mode: ReplayMode = ReplayMode.CANDLE
    state: ReplayControlState = ReplayControlState.IDLE
    index: int = 0
    total: int = 0
    clock: VirtualClock | None = None

    def start(self, *, total: int, start_at: datetime) -> None:
        require(total >= 0, "total must be >= 0")
        self.total = total
        self.index = 0
        self.clock = VirtualClock(current=start_at)
        self.state = (
            ReplayControlState.COMPLETED if total == 0 else ReplayControlState.RUNNING
        )

    def pause(self) -> None:
        if self.state is ReplayControlState.RUNNING and self.clock is not None:
            self.clock.pause()
            self.state = ReplayControlState.PAUSED

    def resume(self) -> None:
        if self.state is ReplayControlState.PAUSED and self.clock is not None:
            self.clock.resume()
            self.state = ReplayControlState.RUNNING

    def set_speed(self, speed: float) -> None:
        if self.clock is not None:
            self.clock.set_speed(speed)

    def step_forward(self) -> int | None:
        """Advance one event index; return new index or None if complete/paused."""
        if self.state is ReplayControlState.PAUSED:
            return None
        if self.state is ReplayControlState.COMPLETED:
            return None
        if self.index >= self.total:
            self.state = ReplayControlState.COMPLETED
            return None
        current = self.index
        self.index += 1
        if self.index >= self.total:
            self.state = ReplayControlState.COMPLETED
        return current

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "state": self.state.value,
            "index": self.index,
            "total": self.total,
            "speed": self.clock.speed if self.clock else 1.0,
            "virtual_time": (self.clock.current.isoformat() if self.clock else None),
            "paused": self.clock.paused if self.clock else False,
        }


@dataclass
class VirtualPortfolio:
    """In-memory virtual account for backtests — never a live broker account."""

    initial_balance: Decimal
    balance: Decimal
    equity: Decimal
    floating_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        require(self.initial_balance > 0, "initial_balance must be > 0")
        if self.peak_equity <= 0:
            self.peak_equity = self.equity

    @classmethod
    def create(cls, *, initial_balance: Decimal) -> Self:
        return cls(
            initial_balance=initial_balance,
            balance=initial_balance,
            equity=initial_balance,
            peak_equity=initial_balance,
        )

    def mark_to_market(self, floating: Decimal, *, margin: Decimal) -> None:
        self.floating_pnl = floating
        self.margin = margin
        self.equity = self.balance + floating
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        if self.peak_equity > 0:
            dd = (self.peak_equity - self.equity) / self.peak_equity * Decimal("100")
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

    def apply_realized(self, pnl: Decimal, *, fee: Decimal) -> None:
        net = pnl - fee
        self.realized_pnl += net
        self.balance += net
        self.equity = self.balance + self.floating_pnl
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

    def to_dict(self) -> dict[str, object]:
        return {
            "initial_balance": str(self.initial_balance),
            "balance": str(self.balance),
            "equity": str(self.equity),
            "floating_pnl": str(self.floating_pnl),
            "realized_pnl": str(self.realized_pnl),
            "margin": str(self.margin),
            "peak_equity": str(self.peak_equity),
            "max_drawdown_pct": str(self.max_drawdown_pct),
        }


@dataclass(eq=False, kw_only=True)
class SimulatedTrade(Entity):
    """Simulated trade record — never sent to a broker."""

    backtest_id: UUID
    symbol: str
    side: SimulatedTradeSide
    status: SimulatedTradeStatus
    volume: Decimal
    entry_price: Decimal
    exit_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    spread: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    pnl: Decimal = Decimal("0")
    exit_reason: SimulatedExitReason | None = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    bar_index_open: int = 0
    bar_index_close: int | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        require(len(self.symbol) > 0, "symbol is required")
        require(self.volume > 0, "volume must be > 0")
        require(self.entry_price > 0, "entry_price must be > 0")

    @classmethod
    def open_trade(
        cls,
        *,
        backtest_id: UUID,
        symbol: str,
        side: SimulatedTradeSide,
        volume: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
        spread: Decimal,
        slippage: Decimal,
        fees: Decimal,
        opened_at: datetime,
        bar_index: int,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "backtest_id": backtest_id,
            "symbol": symbol,
            "side": side,
            "status": SimulatedTradeStatus.OPEN,
            "volume": volume,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "spread": spread,
            "slippage": slippage,
            "fees": fees,
            "opened_at": opened_at,
            "bar_index_open": bar_index,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def close(
        self,
        *,
        exit_price: Decimal,
        pnl: Decimal,
        exit_reason: SimulatedExitReason,
        closed_at: datetime,
        bar_index: int,
        extra_fees: Decimal = Decimal("0"),
    ) -> None:
        require(
            self.status is SimulatedTradeStatus.OPEN,
            "only open trades can be closed",
        )
        self.exit_price = exit_price
        self.pnl = pnl
        self.fees += extra_fees
        self.exit_reason = exit_reason
        self.closed_at = closed_at
        self.bar_index_close = bar_index
        self.status = SimulatedTradeStatus.CLOSED
        self.touch()

    def unrealized_pnl(self, mark: Decimal, *, contract_size: Decimal) -> Decimal:
        direction = (
            Decimal("1") if self.side is SimulatedTradeSide.BUY else Decimal("-1")
        )
        return (mark - self.entry_price) * direction * self.volume * contract_size

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "backtest_id": str(self.backtest_id),
                "symbol": self.symbol,
                "side": self.side.value,
                "status": self.status.value,
                "volume": str(self.volume),
                "entry_price": str(self.entry_price),
                "exit_price": str(self.exit_price) if self.exit_price else None,
                "stop_loss": str(self.stop_loss) if self.stop_loss else None,
                "take_profit": str(self.take_profit) if self.take_profit else None,
                "spread": str(self.spread),
                "slippage": str(self.slippage),
                "fees": str(self.fees),
                "pnl": str(self.pnl),
                "exit_reason": (self.exit_reason.value if self.exit_reason else None),
                "opened_at": self.opened_at.isoformat(),
                "closed_at": (self.closed_at.isoformat() if self.closed_at else None),
                "bar_index_open": self.bar_index_open,
                "bar_index_close": self.bar_index_close,
            }
        )
        return base


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """One point on equity / balance / drawdown curves."""

    timestamp: datetime
    equity: Decimal
    balance: Decimal
    drawdown_pct: Decimal
    bar_index: int

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": str(self.equity),
            "balance": str(self.balance),
            "drawdown_pct": str(self.drawdown_pct),
            "bar_index": self.bar_index,
        }


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Performance metrics for a completed (or partial) backtest."""

    total_return_pct: Decimal = Decimal("0")
    cagr_pct: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None
    profit_factor: Decimal | None = None
    expectancy: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    average_r: Decimal | None = None
    max_drawdown_pct: Decimal = Decimal("0")
    recovery_factor: Decimal | None = None
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "total_return_pct": str(self.total_return_pct),
            "cagr_pct": str(self.cagr_pct) if self.cagr_pct is not None else None,
            "sharpe_ratio": (
                str(self.sharpe_ratio) if self.sharpe_ratio is not None else None
            ),
            "sortino_ratio": (
                str(self.sortino_ratio) if self.sortino_ratio is not None else None
            ),
            "profit_factor": (
                str(self.profit_factor) if self.profit_factor is not None else None
            ),
            "expectancy": str(self.expectancy),
            "win_rate": str(self.win_rate),
            "average_r": str(self.average_r) if self.average_r is not None else None,
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "recovery_factor": (
                str(self.recovery_factor) if self.recovery_factor is not None else None
            ),
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
        }


@dataclass(eq=False, kw_only=True)
class BacktestRun(Entity):
    """Persisted backtest run — history only, never live execution."""

    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str
    status: BacktestStatus
    replay_mode: ReplayMode
    initial_balance: Decimal
    assumptions: dict[str, object] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)
    equity_curve: list[dict[str, object]] = field(default_factory=list)
    portfolio_snapshot: dict[str, object] = field(default_factory=dict)
    trade_count: int = 0
    bar_count: int = 0
    replay_state: dict[str, object] = field(default_factory=dict)
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.timeframe = self.timeframe.strip().lower()
        self.request_id = self.request_id.strip()
        require(len(self.request_id) > 0, "request_id is required")
        require(len(self.symbol) > 0, "symbol is required")
        require(self.initial_balance > 0, "initial_balance must be > 0")

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        timeframe: str,
        initial_balance: Decimal,
        replay_mode: ReplayMode = ReplayMode.CANDLE,
        assumptions: dict[str, object] | None = None,
        bar_count: int = 0,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "status": BacktestStatus.PENDING,
            "replay_mode": replay_mode,
            "initial_balance": initial_balance,
            "assumptions": dict(assumptions or {}),
            "bar_count": bar_count,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def mark_running(self, *, at: datetime | None = None) -> None:
        self.status = BacktestStatus.RUNNING
        self.started_at = at or datetime.now(UTC)
        self.touch()

    def mark_completed(
        self,
        *,
        metrics: BacktestMetrics,
        equity_curve: list[EquityPoint],
        portfolio: VirtualPortfolio,
        trade_count: int,
        replay_state: dict[str, object],
        at: datetime | None = None,
    ) -> None:
        self.status = BacktestStatus.COMPLETED
        self.metrics = metrics.to_dict()
        self.equity_curve = [p.to_dict() for p in equity_curve]
        self.portfolio_snapshot = portfolio.to_dict()
        self.trade_count = trade_count
        self.replay_state = replay_state
        self.finished_at = at or datetime.now(UTC)
        self.touch()

    def mark_failed(self, *, message: str, at: datetime | None = None) -> None:
        self.status = BacktestStatus.FAILED
        self.error_message = message.strip()[:1000]
        self.finished_at = at or datetime.now(UTC)
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "status": self.status.value,
                "replay_mode": self.replay_mode.value,
                "initial_balance": str(self.initial_balance),
                "assumptions": dict(self.assumptions),
                "metrics": dict(self.metrics),
                "equity_curve": list(self.equity_curve),
                "portfolio_snapshot": dict(self.portfolio_snapshot),
                "trade_count": self.trade_count,
                "bar_count": self.bar_count,
                "replay_state": dict(self.replay_state),
                "error_message": self.error_message,
                "started_at": (
                    self.started_at.isoformat() if self.started_at else None
                ),
                "finished_at": (
                    self.finished_at.isoformat() if self.finished_at else None
                ),
            }
        )
        return base
