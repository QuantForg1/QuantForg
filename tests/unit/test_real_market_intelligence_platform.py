"""Unit tests — Real Market Intelligence Platform."""

from __future__ import annotations

from app.domain.real_market_intelligence_platform import (
    RealMarketIntelligencePlatform,
    RmipConfig,
    RmipInput,
)
from app.domain.real_market_intelligence_platform.modules import MISSING
from app.domain.trading.gold_only import GOLD_SYMBOL


def test_hard_locks_context_only() -> None:
    status = RealMarketIntelligencePlatform().status()
    assert status["symbol"] == GOLD_SYMBOL
    assert status["allow_order_send"] is False
    assert status["allow_place_trades"] is False
    assert status["allow_modify_trading_rules"] is False
    assert status["invent_macro_data"] is False
    caps = status["capabilities"]
    assert caps["context_only"] is True
    assert caps["never_modify_risk_engine"] is True
    assert caps["never_fabricate_market_data"] is True
    assert len(status["modules"]) == 10


def test_policies_cannot_unlock() -> None:
    cfg = RmipConfig().update(
        {
            "allow_order_send": True,
            "allow_modify_decision_engine": True,
            "invent_macro_data": True,
        }
    )
    assert cfg.allow_order_send is False
    assert cfg.allow_modify_decision_engine is False
    assert cfg.invent_macro_data is False


def test_missing_feeds_reported() -> None:
    out = RealMarketIntelligencePlatform().evaluate(RmipInput())
    assert (
        out["modules"]["economic_calendar"]["recommendation"] == MISSING
    )
    assert (
        out["modules"]["volatility_observatory"]["recommendation"] == MISSING
    )
    assert out["never_order_send"] is True
    assert out["never_change_trading_rules"] is True


def test_never_guesses_actual() -> None:
    out = RealMarketIntelligencePlatform().evaluate(
        RmipInput(
            economic_events=[
                {
                    "name": "CPI",
                    "currency": "USD",
                    "importance": "high",
                    "scheduled_time": "2026-07-22T12:00:00Z",
                    "previous": "3.1",
                    "forecast": "3.0",
                    # actual omitted on purpose
                }
            ]
        )
    )
    events = out["modules"]["economic_calendar"]["details"]["events"]
    assert events[0]["actual"] is None
    assert out["modules"]["economic_calendar"]["details"][
        "never_guesses_missing_values"
    ] is True
    assert out["modules"]["economic_calendar"]["details"][
        "market_risk_level"
    ] == "HIGH"


def test_full_context_cycle() -> None:
    rmip = RealMarketIntelligencePlatform()
    out = rmip.evaluate(
        RmipInput(
            clock_utc="2026-07-22T13:30:00+00:00",
            session_hint="london",
            regime="trend",
            trend="Bullish",
            confidence="moderate",
            economic_events=[
                {
                    "name": "NFP",
                    "currency": "USD",
                    "importance": "critical",
                    "scheduled_time": "2026-07-22T12:30:00Z",
                    "previous": "180K",
                    "forecast": "175K",
                    "actual": None,
                }
            ],
            volatility_observations={
                "average_daily_range": 30,
                "current_session_range": 10,
                "atr": 5,
                "spread_expansion": 0.1,
                "price_acceleration": 0.2,
                "level": "normal",
            },
            liquidity_observations={
                "session_liquidity": "deep",
                "daily_high": 2400,
                "daily_low": 2380,
                "weekly_high": 2410,
                "weekly_low": 2360,
                "liquidity_sweep": False,
                "range_compression": False,
                "expansion": True,
                "liquidity_quality": "Excellent",
            },
            archive_event={"comments": "test"},
        )
    )
    assert out["context_only"] is True
    assert out["modifies_execution"] is False
    assert out["modules"]["session_intelligence"]["status"] == "available"
    assert out["modules"]["context_scoring"]["status"] == "available"
    assert out["modules"]["explainability"]["details"]["confidence"] is not None
    assert out["modules"]["context_api"]["details"]["read_only"] is True
    assert out["modules"]["operator_intelligence_feed"]["status"] == "available"
    assert len(rmip.archive) == 1
    first = rmip.archive[0]["id"]
    rmip.evaluate(
        RmipInput(
            clock_utc="2026-07-22T14:00:00+00:00",
            volatility_observations={"atr": 5, "level": "elevated"},
        )
    )
    assert len(rmip.archive) == 2
    assert any(a["id"] == first for a in rmip.archive)
