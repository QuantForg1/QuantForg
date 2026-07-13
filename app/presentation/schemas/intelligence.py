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


class IntelligenceEventResponse(BaseModel):
    id: str
    title: str
    summary: str = ""
    classification: str
    severity: str
    affected_currencies: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    expected_volatility: str = ""
    portfolio_impact: str = ""
    risk_score: float = 0.0
    provider: str = ""
    source_url: str = ""
    published_at: str = ""
    deterministic_summary: str = ""


class ProviderHealthResponse(BaseModel):
    name: str
    kind: str
    status: str
    configured: bool
    priority: int
    latency_ms: float | None = None
    last_error: str = ""
    last_success_at: str = ""
    requests: int = 0
    failures: int = 0
    cache_hits: int = 0
    rate_limited: int = 0


class IntelligenceStatusResponse(BaseModel):
    provider_count: int
    configured_count: int
    healthy_count: int
    kinds: dict[str, Any] = Field(default_factory=dict)
    failover: str = "priority_ascending"
    caching: str = "ttl"
    rate_limits: str = "token_bucket"
    timeouts: str = "per_provider"
