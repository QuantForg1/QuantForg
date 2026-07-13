"""Strategy Engine ports — plugins produce intentions only (ADR-0012)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar, Protocol


class EngineSignalAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class OhlcBar:
    """Minimal OHLC bar for deterministic strategies (caller-supplied or MT5)."""

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    time: str = ""


@dataclass(frozen=True, slots=True)
class StrategySnapshot:
    """Immutable input snapshot for a strategy plugin."""

    symbol: str
    timeframe: str
    bars: tuple[OhlcBar, ...]
    params: dict[str, Any] = field(default_factory=dict)
    session: str = "unknown"
    market_state: str = "unknown"
    as_of: str = ""


@dataclass(frozen=True, slots=True)
class SignalExplanation:
    reason: str
    indicator: str
    threshold: str
    market_context: str
    value: str = ""


@dataclass(frozen=True, slots=True)
class StrategyIntention:
    """Non-executing strategy output (never places trades)."""

    action: EngineSignalAction
    confidence: float
    explanations: tuple[SignalExplanation, ...]
    strategy_key: str
    symbol: str
    timeframe: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategyRiskLimits:
    max_risk_pct: float = 1.0
    max_trades: int = 5
    daily_loss_pct: float = 3.0
    max_exposure_pct: float = 20.0
    max_correlation: float = 0.8


@dataclass(frozen=True, slots=True)
class StrategyRiskVerdict:
    allowed: bool
    reasons: tuple[str, ...]
    adjusted_confidence: float
    limits: StrategyRiskLimits


class StrategyPort(Protocol):
    """Deterministic strategy plugin — no MT5/SQL/execution imports."""

    key: ClassVar[str]
    name: ClassVar[str]
    category: ClassVar[str]
    description: ClassVar[str]
    default_params: ClassVar[dict[str, Any]]

    def validate_params(
        self, params: dict[str, Any]
    ) -> tuple[bool, tuple[str, ...]]: ...

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention: ...


class RuleCondition(Protocol):
    def evaluate(self, snapshot: StrategySnapshot, ctx: dict[str, Any]) -> bool: ...


class StrategyRiskPort(Protocol):
    def check(
        self,
        intention: StrategyIntention,
        *,
        open_trades: int,
        daily_pnl_pct: float,
        exposure_pct: float,
        limits: StrategyRiskLimits,
        correlation: float | None = None,
    ) -> StrategyRiskVerdict: ...
