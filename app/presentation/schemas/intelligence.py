"""Market Intelligence REST schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketContextResponse(BaseModel):
    market_code: str
    session: str
    market_state: str
    day_type: str
    liquidity_level: str
    volatility_level: str
    timezone: str
    as_of_utc: str
    local_time: str
    symbol: str | None = None


class NewsItemResponse(BaseModel):
    id: str
    title: str
    summary: str = ""
    source: str = ""
    url: str = ""
    published_at: str = ""
    symbols: list[str] = Field(default_factory=list)


class EconomicEventResponse(BaseModel):
    id: str
    title: str
    country: str = ""
    impact: str = "unknown"
    scheduled_at: str = ""
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    source: str = ""


class IntelligenceDashboardResponse(BaseModel):
    broker: dict[str, Any]
    account: dict[str, Any] = Field(default_factory=dict)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    pending_orders: list[dict[str, Any]] = Field(default_factory=list)
    history: dict[str, Any] = Field(default_factory=dict)
    market_context: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)
    news: list[dict[str, Any]] = Field(default_factory=list)
    economic_events: list[dict[str, Any]] = Field(default_factory=list)
    providers: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    advisor: str
    autonomous_trading: bool = False
    market_conditions: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    news_impact: list[str] = Field(default_factory=list)
    portfolio_exposure: list[str] = Field(default_factory=list)
    disclaimer: str = ""
