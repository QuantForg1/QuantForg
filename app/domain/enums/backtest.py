"""Backtesting enumerations — offline simulation only, never live trading."""

from __future__ import annotations

from enum import StrEnum


class BacktestStatus(StrEnum):
    """Lifecycle status of a backtest run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReplayMode(StrEnum):
    """Historical replay data mode."""

    CANDLE = "candle"
    TICK = "tick"


class ReplayControlState(StrEnum):
    """Virtual replay controller state."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class SimulatedTradeSide(StrEnum):
    """Side of a simulated trade."""

    BUY = "buy"
    SELL = "sell"


class SimulatedTradeStatus(StrEnum):
    """Lifecycle of a simulated trade."""

    OPEN = "open"
    CLOSED = "closed"


class SimulatedExitReason(StrEnum):
    """Why a simulated trade closed."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    SIGNAL = "signal"
    END_OF_DATA = "end_of_data"
    MANUAL = "manual"
