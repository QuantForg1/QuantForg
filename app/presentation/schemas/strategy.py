"""HTTP schemas for the Strategy Runtime Engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StrategyEvaluateRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="m15", max_length=16)
    market_open: bool = True
    session: str = Field(default="unknown", max_length=32)
    structure_bias: str = Field(
        default="unknown",
        description="up | down | range | unknown (from Market Structure)",
    )
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
    analysis_notes: list[str] = Field(default_factory=list, max_length=20)
    check_risk: bool = True
    requested_lots: str | None = None
    stop_loss_distance: str | None = None
    entry_price: str | None = None
    equity: str | None = Field(
        default=None, description="Optional equity override for offline evaluation"
    )
    balance: str | None = None
    tick_age_seconds: float | None = Field(
        default=None, description="Optional tick age override (tests / offline)"
    )
    candle_count: int | None = None
    last_price: str | None = None


class StrategySignalResponse(BaseModel):
    id: UUID
    symbol: str
    timeframe: str
    direction: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    generated_at: datetime
    evaluation_id: UUID | None = None
    rejected: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)


class StrategyEvaluateResponse(BaseModel):
    id: UUID
    request_id: str
    symbol: str
    timeframe: str
    decision: str = Field(description="no_action | watch | ready | blocked")
    reasons: list[str] = Field(default_factory=list)
    preconditions: dict[str, bool] = Field(default_factory=dict)
    market_state: dict[str, object] = Field(default_factory=dict)
    signal: StrategySignalResponse | None = None
    risk_decision: str | None = None
    risk_score: int | None = None
    evaluated_at: datetime


class StrategySignalListResponse(BaseModel):
    items: list[StrategySignalResponse]
    count: int
