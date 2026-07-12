"""Strategy Runtime domain models — decisions and signals only, never execute."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.signal import SignalDirection
from app.domain.enums.strategy import StrategyDecisionType


@dataclass(frozen=True, slots=True)
class StrategyRuntimeConfig:
    """Runtime thresholds for strategy evaluation (no trading parameters)."""

    max_tick_age_seconds: float = 120.0
    min_confluence: int = 2
    min_ready_confidence: float = 0.55
    min_watch_confidence: float = 0.30
    require_fresh_data: bool = True
    consult_risk_engine: bool = True


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Normalized analysis inputs consumed by the Strategy Runtime.

    Built from Market Context, Structure, Liquidity, Order Blocks, and FVGs.
    Values are descriptive facts — not AI output.
    """

    market_open: bool = True
    session: str = "unknown"
    structure_bias: str = "unknown"  # up | down | range | unknown
    liquidity_sweep_bullish: bool = False
    liquidity_sweep_bearish: bool = False
    order_block_bullish: bool = False
    order_block_bearish: bool = False
    fvg_bullish: bool = False
    fvg_bearish: bool = False
    has_structure: bool = False
    has_liquidity: bool = False
    has_order_blocks: bool = False
    has_fvgs: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "market_open": self.market_open,
            "session": self.session,
            "structure_bias": self.structure_bias,
            "liquidity_sweep_bullish": self.liquidity_sweep_bullish,
            "liquidity_sweep_bearish": self.liquidity_sweep_bearish,
            "order_block_bullish": self.order_block_bullish,
            "order_block_bearish": self.order_block_bearish,
            "fvg_bullish": self.fvg_bullish,
            "fvg_bearish": self.fvg_bearish,
            "has_structure": self.has_structure,
            "has_liquidity": self.has_liquidity,
            "has_order_blocks": self.has_order_blocks,
            "has_fvgs": self.has_fvgs,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class MarketState:
    """Collected market/portfolio snapshot used for one evaluation."""

    symbol: str
    timeframe: str
    tick_age_seconds: float | None
    last_price: str | None
    candle_count: int
    position_count: int
    equity: str | None
    analysis: AnalysisContext
    collected_at: datetime
    data_fresh: bool
    freshness_reasons: tuple[str, ...] = ()
    mt5_connected: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "tick_age_seconds": self.tick_age_seconds,
            "last_price": self.last_price,
            "candle_count": self.candle_count,
            "position_count": self.position_count,
            "equity": self.equity,
            "analysis": self.analysis.to_dict(),
            "collected_at": self.collected_at.isoformat(),
            "data_fresh": self.data_fresh,
            "freshness_reasons": list(self.freshness_reasons),
            "mt5_connected": self.mt5_connected,
        }


@dataclass(eq=False, kw_only=True)
class StrategySignal(Entity):
    """Runtime strategy signal — suggestion only, never an order."""

    user_id: UUID
    symbol: str
    timeframe: str
    direction: SignalDirection
    confidence: float
    reasons: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    evaluation_id: UUID | None = None
    rejected: bool = False
    rejection_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.timeframe = self.timeframe.strip().lower()
        require(len(self.symbol) > 0, "symbol is required")
        require(len(self.timeframe) > 0, "timeframe is required")
        require(0.0 <= self.confidence <= 1.0, "confidence must be 0-1")
        self.reasons = [r.strip()[:500] for r in self.reasons if r.strip()][:50]
        self.rejection_reasons = [
            r.strip()[:500] for r in self.rejection_reasons if r.strip()
        ][:50]

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        symbol: str,
        timeframe: str,
        direction: SignalDirection,
        confidence: float,
        reasons: list[str] | None = None,
        evaluation_id: UUID | None = None,
        generated_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "confidence": confidence,
            "reasons": list(reasons or []),
            "evaluation_id": evaluation_id,
            "generated_at": generated_at or datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def reject(self, *, reasons: list[str]) -> None:
        self.rejected = True
        self.rejection_reasons = [r.strip()[:500] for r in reasons if r.strip()][:50]
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "direction": self.direction.value,
                "confidence": self.confidence,
                "reasons": list(self.reasons),
                "generated_at": self.generated_at.isoformat(),
                "evaluation_id": (
                    str(self.evaluation_id) if self.evaluation_id else None
                ),
                "rejected": self.rejected,
                "rejection_reasons": list(self.rejection_reasons),
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class StrategyEvaluation(Entity):
    """Persisted Strategy Runtime evaluation — decision history only."""

    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str
    decision: StrategyDecisionType
    reasons: list[str] = field(default_factory=list)
    preconditions: dict[str, bool] = field(default_factory=dict)
    market_state: dict[str, object] = field(default_factory=dict)
    signal_id: UUID | None = None
    risk_decision: str | None = None
    risk_score: int | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.timeframe = self.timeframe.strip().lower()
        self.request_id = self.request_id.strip()
        require(len(self.request_id) > 0, "request_id is required")
        require(len(self.symbol) > 0, "symbol is required")
        require(len(self.timeframe) > 0, "timeframe is required")
        self.reasons = [r.strip()[:500] for r in self.reasons if r.strip()][:50]

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        timeframe: str,
        decision: StrategyDecisionType,
        reasons: list[str] | None = None,
        preconditions: dict[str, bool] | None = None,
        market_state: dict[str, object] | None = None,
        signal_id: UUID | None = None,
        risk_decision: str | None = None,
        risk_score: int | None = None,
        evaluated_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "decision": decision,
            "reasons": list(reasons or []),
            "preconditions": dict(preconditions or {}),
            "market_state": dict(market_state or {}),
            "signal_id": signal_id,
            "risk_decision": risk_decision,
            "risk_score": risk_score,
            "evaluated_at": evaluated_at or datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "decision": self.decision.value,
                "reasons": list(self.reasons),
                "preconditions": dict(self.preconditions),
                "market_state": dict(self.market_state),
                "signal_id": str(self.signal_id) if self.signal_id else None,
                "risk_decision": self.risk_decision,
                "risk_score": self.risk_score,
                "evaluated_at": self.evaluated_at.isoformat(),
            }
        )
        return base
