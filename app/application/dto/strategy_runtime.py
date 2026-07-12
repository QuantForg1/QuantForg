"""Application DTOs for the Strategy Runtime Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.strategy_runtime import (
    AnalysisContext,
    StrategyEvaluation,
    StrategySignal,
)


@dataclass(frozen=True, slots=True)
class StrategyEvaluateCommand:
    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str = "m15"
    market_open: bool = True
    session: str = "unknown"
    structure_bias: str = "unknown"
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
    analysis_notes: tuple[str, ...] = ()
    check_risk: bool = True
    requested_lots: str | None = None
    stop_loss_distance: str | None = None
    entry_price: str | None = None
    equity: str | None = None
    balance: str | None = None
    tick_age_seconds: float | None = None
    candle_count: int | None = None
    last_price: str | None = None
    mt5_connected: bool | None = None
    position_count: int | None = None
    ip_address: str = ""
    user_agent: str = ""

    def to_analysis(self) -> AnalysisContext:
        return AnalysisContext(
            market_open=self.market_open,
            session=self.session.strip().lower() or "unknown",
            structure_bias=self.structure_bias.strip().lower() or "unknown",
            liquidity_sweep_bullish=self.liquidity_sweep_bullish,
            liquidity_sweep_bearish=self.liquidity_sweep_bearish,
            order_block_bullish=self.order_block_bullish,
            order_block_bearish=self.order_block_bearish,
            fvg_bullish=self.fvg_bullish,
            fvg_bearish=self.fvg_bearish,
            has_structure=self.has_structure,
            has_liquidity=self.has_liquidity,
            has_order_blocks=self.has_order_blocks,
            has_fvgs=self.has_fvgs,
            notes=self.analysis_notes,
        )


@dataclass(frozen=True, slots=True)
class StrategySignalDTO:
    id: UUID
    symbol: str
    timeframe: str
    direction: str
    confidence: float
    reasons: list[str]
    generated_at: datetime
    evaluation_id: UUID | None
    rejected: bool
    rejection_reasons: list[str]

    @classmethod
    def from_entity(cls, entity: StrategySignal) -> StrategySignalDTO:
        return cls(
            id=entity.id,
            symbol=entity.symbol,
            timeframe=entity.timeframe,
            direction=entity.direction.value,
            confidence=entity.confidence,
            reasons=list(entity.reasons),
            generated_at=entity.generated_at,
            evaluation_id=entity.evaluation_id,
            rejected=entity.rejected,
            rejection_reasons=list(entity.rejection_reasons),
        )


@dataclass(frozen=True, slots=True)
class StrategyEvaluateDTO:
    id: UUID
    request_id: str
    symbol: str
    timeframe: str
    decision: str
    reasons: list[str]
    preconditions: dict[str, bool]
    market_state: dict[str, object]
    signal: StrategySignalDTO | None
    risk_decision: str | None
    risk_score: int | None
    evaluated_at: datetime

    @classmethod
    def from_entities(
        cls,
        evaluation: StrategyEvaluation,
        signal: StrategySignal | None,
    ) -> StrategyEvaluateDTO:
        return cls(
            id=evaluation.id,
            request_id=evaluation.request_id,
            symbol=evaluation.symbol,
            timeframe=evaluation.timeframe,
            decision=evaluation.decision.value,
            reasons=list(evaluation.reasons),
            preconditions=dict(evaluation.preconditions),
            market_state=dict(evaluation.market_state),
            signal=StrategySignalDTO.from_entity(signal) if signal else None,
            risk_decision=evaluation.risk_decision,
            risk_score=evaluation.risk_score,
            evaluated_at=evaluation.evaluated_at,
        )


@dataclass(frozen=True, slots=True)
class ListStrategySignalsCommand:
    user_id: UUID
    limit: int = 50
    include_rejected: bool = True
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class StrategySignalListDTO:
    items: list[StrategySignalDTO] = field(default_factory=list)
    count: int = 0
