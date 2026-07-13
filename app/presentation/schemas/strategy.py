"""HTTP schemas for the Strategy Runtime Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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


# --- Strategy Engine (deterministic TA plugins; additive) ---


class OhlcBarRequest(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    time: str = ""


class StrategyRiskLimitsRequest(BaseModel):
    max_risk_pct: float = Field(default=1.0, gt=0, le=100)
    max_trades: int = Field(default=5, ge=0, le=500)
    daily_loss_pct: float = Field(default=3.0, gt=0, le=100)
    max_exposure_pct: float = Field(default=20.0, gt=0, le=100)
    max_correlation: float = Field(default=0.8, ge=0, le=1)


class StrategyEngineRunRequest(BaseModel):
    strategy_key: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="H1", max_length=16)
    bars: list[OhlcBarRequest] = Field(
        default_factory=list,
        description="Caller-supplied OHLC (or empty to load from MT5 when connected)",
        max_length=5000,
    )
    params: dict[str, Any] = Field(default_factory=dict)
    session: str = Field(default="unknown", max_length=32)
    market_state: str = Field(default="unknown", max_length=64)
    open_trades: int = Field(default=0, ge=0)
    daily_pnl_pct: float = 0.0
    exposure_pct: float = Field(default=0.0, ge=0)
    correlation: float | None = Field(default=None, ge=-1, le=1)
    limits: StrategyRiskLimitsRequest | None = None
    allocation_weight_pct: float | None = Field(default=None, ge=0, le=100)
    use_mt5_bars: bool = Field(
        default=True,
        description=(
            "When bars empty, attempt MT5 historical candles "
            "(never fabricated)"
        ),
    )
    mt5_bar_count: int = Field(default=200, ge=5, le=5000)


class StrategyEngineValidateRequest(BaseModel):
    strategy_key: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class StrategyAllocationItem(BaseModel):
    strategy_key: str = Field(min_length=1, max_length=64)
    weight_pct: float = Field(ge=0, le=100)
    symbols: list[str] = Field(default_factory=list, max_length=64)


class StrategyAllocationPutRequest(BaseModel):
    allocations: list[StrategyAllocationItem] = Field(
        default_factory=list, max_length=50
    )
