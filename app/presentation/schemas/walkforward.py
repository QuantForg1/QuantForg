"""HTTP schemas for Walk-Forward Validation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WalkForwardBarRequest(BaseModel):
    open_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str = "0"
    close_time: str | None = None


class WalkForwardRunRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="m15", max_length=16)
    initial_balance: str = "10000"
    bars: list[WalkForwardBarRequest] = Field(default_factory=list)
    in_sample_bars: int = Field(default=40, ge=5, le=5000)
    out_of_sample_bars: int = Field(default=20, ge=2, le=2000)
    step_bars: int = Field(default=20, ge=1, le=2000)
    anchored: bool = False
    optimize_params: bool = True
    auto_analysis: bool = True


class WalkForwardRunResponse(BaseModel):
    id: UUID
    request_id: str
    symbol: str
    timeframe: str
    status: str
    promotion: str | None = Field(
        default=None,
        description="promote_to_paper | needs_rework | reject",
    )
    window_config: dict[str, object] = Field(default_factory=dict)
    folds: list[dict[str, object]] = Field(default_factory=list)
    aggregated_is: dict[str, object] = Field(default_factory=dict)
    aggregated_oos: dict[str, object] = Field(default_factory=dict)
    robustness: dict[str, object] = Field(default_factory=dict)
    combined_equity: list[dict[str, object]] = Field(default_factory=list)
    report: dict[str, object] = Field(default_factory=dict)
    bar_count: int = 0
    fold_count: int = 0
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WalkForwardListResponse(BaseModel):
    items: list[WalkForwardRunResponse]
    count: int
