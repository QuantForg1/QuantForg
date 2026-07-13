"""HTTP schemas for Portfolio Intelligence laboratory."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    max_risk_pct: float = Field(default=100.0, gt=0, le=100)
    max_allocation_pct: float = Field(default=40.0, gt=0, le=100)
    target_volatility: float | None = Field(default=None, ge=0)
    target_return: float | None = None
    # Optional offline snapshot (real caller-supplied data only)
    account: dict[str, Any] | None = None
    positions: list[dict[str, Any]] | None = None
    deals: list[dict[str, Any]] | None = None


class LabSnapshotRequest(BaseModel):
    """Optional offline analysis using caller-supplied real snapshots."""

    account: dict[str, Any] | None = None
    positions: list[dict[str, Any]] = Field(default_factory=list)
    deals: list[dict[str, Any]] = Field(default_factory=list)
    paper_trades: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.95, gt=0.5, lt=1.0)
    max_risk_pct: float = Field(default=100.0, gt=0, le=100)
    max_allocation_pct: float = Field(default=40.0, gt=0, le=100)
    target_volatility: float | None = None
    target_return: float | None = None
