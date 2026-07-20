"""HTTP schemas for the Risk Management Engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RiskCheckRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(description="buy | sell")
    requested_lots: str | None = None
    stop_loss_distance: str | None = None
    atr: str | None = None
    spread: str | None = None
    sizing_method: str = Field(
        default="percentage_risk",
        description="fixed_lot | fixed_dollar_risk | percentage_risk | atr_based",
    )
    entry_price: str = Field(default="1.0")
    peak_equity: str | None = None
    daily_pnl: str = "0"
    weekly_pnl: str = "0"
    monthly_pnl: str = "0"
    equity: str | None = Field(
        default=None, description="Optional equity override for offline checks"
    )
    balance: str | None = None


class RiskCheckResponse(BaseModel):
    id: UUID
    request_id: str
    symbol: str
    side: str
    decision: str = Field(description="allow | reduce_size | reject")
    risk_score: int = Field(ge=0, le=100)
    risk_band: str = Field(description="low | medium | high | blocked")
    approved_lots: str
    requested_lots: str
    sizing_method: str
    warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    exposure: dict[str, object] = Field(default_factory=dict)
    drawdown: dict[str, object] = Field(default_factory=dict)
    checks: dict[str, bool] = Field(default_factory=dict)
    rules: list[dict[str, object]] = Field(
        default_factory=list,
        description="Per-rule PASS/FAIL with current vs threshold",
    )
    assessed_at: datetime
