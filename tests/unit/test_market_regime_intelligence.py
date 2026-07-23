"""Unit tests — Market Regime Intelligence Engine (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.market_regime_intelligence import (
    ALL_REGIMES,
    REGIME_BREAKOUT,
    REGIME_HIGH_VOL,
    REGIME_PULLBACK,
    REGIME_RANGING,
    REGIME_TRENDING,
    REGIME_UNKNOWN,
    build_market_regime_intelligence,
    classify_regime,
    evaluation_card,
    historical_performance_by_regime,
)


def _cycle(**overrides):
    base = {
        "recorded_at": "2026-07-23T18:00:00+00:00",
        "signal_id": "sig-regime",
        "decision_action": "NO_TRADE",
        "market_session": "london_ny_overlap",
        "trend": {
            "aligned": True,
            "score": 88,
            "h4": "up",
            "h1": "up",
            "m15": "up",
            "m5": "up",
        },
        "quality": {"score": 80, "required": 75, "passed": True},
        "confluence": {
            "total": 82,
            "required": 75,
            "passed": True,
            "components": {
                "bos": 20,
                "choch": 10,
                "liquidity_sweep": 0,
                "fair_value_gap": 50,
                "volume": 40,
                "news_filter": 100,
            },
        },
        "atr": 30.0,
        "market_context_diagnostics": {
            "bid": 4000.0,
            "ask": 4000.4,
            "spread": 0.4,
            "atr": 30.0,
        },
        "sizing": {"atr": 30.0},
    }
    base.update(overrides)
    return base


def test_classify_trending():
    c = classify_regime(_cycle())
    assert c["primary"] == REGIME_TRENDING
    assert c["confidence"] >= 70
    assert c["never_influences_execution"] is True


def test_classify_ranging():
    c = classify_regime(
        _cycle(
            trend={
                "aligned": False,
                "score": 48,
                "h4": "range",
                "h1": "range",
                "m15": "range",
                "m5": "range",
            }
        )
    )
    assert c["primary"] == REGIME_RANGING


def test_classify_breakout_with_high_vol_secondary():
    c = classify_regime(
        _cycle(
            atr=80.0,  # 80/4000 = 2% → high vol
            market_context_diagnostics={
                "bid": 4000.0,
                "ask": 4000.5,
                "spread": 0.5,
                "atr": 80.0,
            },
            confluence={
                "total": 85,
                "required": 75,
                "passed": True,
                "components": {
                    "bos": 90,
                    "choch": 0,
                    "liquidity_sweep": 0,
                    "fair_value_gap": 40,
                    "volume": 60,
                    "news_filter": 100,
                },
            },
        )
    )
    assert c["primary"] == REGIME_BREAKOUT
    assert c["secondary"] == REGIME_HIGH_VOL


def test_classify_pullback():
    c = classify_regime(
        _cycle(
            trend={
                "aligned": False,
                "score": 62,
                "h4": "up",
                "h1": "up",
                "m15": "down",
                "m5": "down",
            }
        )
    )
    assert c["primary"] == REGIME_PULLBACK


def test_evaluation_card_and_performance():
    trades = [
        {
            "regime_primary": REGIME_TRENDING,
            "profit_loss": 20.0,
            "risk_reward": 2.1,
        },
        {
            "regime_primary": REGIME_TRENDING,
            "profit_loss": 15.0,
            "risk_reward": 1.8,
        },
        {
            "regime_primary": REGIME_TRENDING,
            "profit_loss": -8.0,
            "risk_reward": -1.0,
        },
        {
            "regime_primary": REGIME_RANGING,
            "profit_loss": -12.0,
            "risk_reward": -1.2,
        },
        {
            "regime_primary": REGIME_RANGING,
            "profit_loss": -5.0,
            "risk_reward": -0.8,
        },
    ]
    perf = historical_performance_by_regime(trades)
    assert perf[REGIME_TRENDING]["win_rate_pct"] == 66.7
    assert perf[REGIME_TRENDING]["profit_factor"] is not None
    assert perf[REGIME_TRENDING]["expectancy_r"] is not None

    card = evaluation_card(_cycle(), performance=perf)
    assert card["current_regime"] == REGIME_TRENDING
    assert card["confidence_display"].endswith("%")
    assert card["historical_performance"]["win_rate_pct"] == 66.7


def test_dashboard_payload_shape():
    now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
    cycles = []
    for i in range(5):
        c = _cycle(
            recorded_at=(now + timedelta(minutes=i)).isoformat(),
            signal_id=f"s-{i}",
            trend={
                "aligned": i % 2 == 0,
                "score": 80 if i % 2 == 0 else 45,
                "h4": "up",
                "h1": "up" if i % 2 == 0 else "range",
                "m15": "up",
                "m5": "up",
            },
        )
        cycles.append(c)
    # newest first
    cycles = list(reversed(cycles))
    payload = build_market_regime_intelligence(
        diagnostics={"cycles": cycles},
        closed_trades=[],
        skip_sic_trade_load=True,
    )
    assert payload["mode"] == "market_regime_intelligence"
    assert payload["never_influences_trade_decisions"] is True
    assert payload["mutates_engines"] is False
    assert payload["count"] == 5
    assert payload["current"]["current_regime"] in {
        *ALL_REGIMES,
        REGIME_UNKNOWN,
    }
    assert len(payload["regime_distribution"]) >= 1
    assert len(payload["regime_history"]) == 5
