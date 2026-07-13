"""Unit tests for Market Intelligence advisor and null feeds."""

from __future__ import annotations

from app.application.services.ai_market_advisor import AiMarketAdvisor
from app.application.services.news_intelligence import NewsIntelligenceService
from app.infrastructure.news.configured_feed import NullEconomicCalendar, NullNewsFeed


def test_null_feeds_return_empty() -> None:
    svc = NewsIntelligenceService(
        news_feed=NullNewsFeed(),
        calendar=NullEconomicCalendar(),
    )
    assert svc.news() == []
    assert svc.economic_events() == []
    status = svc.provider_status()
    assert status["news_configured"] is False
    assert status["calendar_configured"] is False


def test_advisor_never_claims_autonomous_trading() -> None:
    analysis = AiMarketAdvisor().summarize(
        {
            "broker": {"connected": False},
            "account": {},
            "market_context": {
                "market_code": "FX",
                "session": "london",
                "market_state": "open",
                "volatility_level": "medium",
                "liquidity_level": "high",
            },
            "market": {},
            "news": [],
            "economic_events": [],
            "positions": [],
            "pending_orders": [],
        }
    )
    assert analysis["autonomous_trading"] is False
    assert "will not invent" in " ".join(analysis["news_impact"]).lower() or (
        "not invent" in analysis["disclaimer"].lower()
        or "will not invent" in " ".join(analysis["news_impact"]).lower()
    )
    assert any("disconnected" in line.lower() for line in analysis["market_conditions"])
