"""Broker Connectivity Framework HTTP schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InvokeConnectivityRequest(BaseModel):
    platform: str = Field(..., min_length=1, max_length=64)
    capability: str = Field(..., min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    symbol: str = ""
    timeframe: str = "H1"
    count: int = Field(default=100, ge=1, le=5000)
    limit: int = Field(default=100, ge=1, le=1000)
    intent: dict[str, Any] = Field(default_factory=dict)


class ConnectivityTradingRequest(BaseModel):
    """Trading probe — never places orders; reports gate only."""

    intent: dict[str, Any] = Field(default_factory=dict)


class RunCertificationRequest(BaseModel):
    """Run certification against the live MT5 session (no simulated data)."""

    broker: str | None = Field(default=None, max_length=64)
    symbol: str = Field(default="EURUSD", min_length=1, max_length=32)
    tester: str = Field(default="operator", min_length=1, max_length=128)
