"""Application DTOs for the Backtesting Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.backtest import BacktestRun, SimulatedTrade


@dataclass(frozen=True, slots=True)
class BacktestBarCommand:
    open_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str = "0"
    close_time: str | None = None


@dataclass(frozen=True, slots=True)
class RunBacktestCommand:
    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str = "m15"
    initial_balance: str = "10000"
    bars: tuple[BacktestBarCommand, ...] = ()
    ticks: tuple[dict[str, object], ...] = ()
    replay_mode: str = "candle"
    spread: str = "0.00010"
    slippage: str = "0.00005"
    fee_per_lot: str = "7"
    lot_size: str = "0.10"
    stop_loss_distance: str = "0.0020"
    take_profit_distance: str = "0.0040"
    auto_analysis: bool = True
    max_open_trades: int = 1
    consult_execution_safety: bool = True
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class SimulatedTradeDTO:
    id: UUID
    symbol: str
    side: str
    status: str
    volume: str
    entry_price: str
    exit_price: str | None
    stop_loss: str | None
    take_profit: str | None
    spread: str
    slippage: str
    fees: str
    pnl: str
    exit_reason: str | None
    opened_at: datetime
    closed_at: datetime | None

    @classmethod
    def from_entity(cls, entity: SimulatedTrade) -> SimulatedTradeDTO:
        return cls(
            id=entity.id,
            symbol=entity.symbol,
            side=entity.side.value,
            status=entity.status.value,
            volume=str(entity.volume),
            entry_price=str(entity.entry_price),
            exit_price=str(entity.exit_price) if entity.exit_price else None,
            stop_loss=str(entity.stop_loss) if entity.stop_loss else None,
            take_profit=str(entity.take_profit) if entity.take_profit else None,
            spread=str(entity.spread),
            slippage=str(entity.slippage),
            fees=str(entity.fees),
            pnl=str(entity.pnl),
            exit_reason=(entity.exit_reason.value if entity.exit_reason else None),
            opened_at=entity.opened_at,
            closed_at=entity.closed_at,
        )


@dataclass(frozen=True, slots=True)
class BacktestRunDTO:
    id: UUID
    request_id: str
    symbol: str
    timeframe: str
    status: str
    replay_mode: str
    initial_balance: str
    metrics: dict[str, object]
    equity_curve: list[dict[str, object]]
    portfolio_snapshot: dict[str, object]
    trades: list[SimulatedTradeDTO]
    trade_count: int
    bar_count: int
    replay_state: dict[str, object]
    assumptions: dict[str, object]
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_entities(
        cls,
        run: BacktestRun,
        trades: list[SimulatedTrade] | None = None,
    ) -> BacktestRunDTO:
        return cls(
            id=run.id,
            request_id=run.request_id,
            symbol=run.symbol,
            timeframe=run.timeframe,
            status=run.status.value,
            replay_mode=run.replay_mode.value,
            initial_balance=str(run.initial_balance),
            metrics=dict(run.metrics),
            equity_curve=list(run.equity_curve),
            portfolio_snapshot=dict(run.portfolio_snapshot),
            trades=[SimulatedTradeDTO.from_entity(t) for t in (trades or [])],
            trade_count=run.trade_count,
            bar_count=run.bar_count,
            replay_state=dict(run.replay_state),
            assumptions=dict(run.assumptions),
            error_message=run.error_message,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


@dataclass(frozen=True, slots=True)
class ListBacktestsCommand:
    user_id: UUID
    limit: int = 50
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class GetBacktestCommand:
    user_id: UUID
    backtest_id: UUID
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class BacktestListDTO:
    items: list[BacktestRunDTO] = field(default_factory=list)
    count: int = 0
