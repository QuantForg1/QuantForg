"""Unit tests — institutional autonomy extensions (trace, explain, calendar, pause)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.continuous_operation import (
    ContinuousOperationController,
)
from app.domain.institutional_trading.ai_scalping.decision_explain import (
    classify_explain_action,
    explain_decision,
)
from app.domain.institutional_trading.ai_scalping.economic_calendar_adapter import (
    EconomicCalendarNewsAdapter,
)
from app.domain.institutional_trading.ai_scalping.execution_trace import (
    build_institutional_execution_trace,
)
from app.domain.institutional_trading.ai_scalping.spread_intelligence import (
    assess_spread,
)


@pytest.mark.unit
def test_explain_actions_cover_taxonomy() -> None:
    assert classify_explain_action(direction="BUY") == "BUY"
    assert classify_explain_action(direction="SELL") == "SELL"
    assert classify_explain_action(reject=True) == "NO_TRADE"
    assert classify_explain_action(manage_action="partial_close") == "PARTIAL"
    assert classify_explain_action(manage_action="trail") == "MOVE_SL"
    assert classify_explain_action(manage_action="close") == "CLOSE"
    out = explain_decision(direction="BUY", reasons=["MTF aligned"])
    assert out["action"] == "BUY"
    assert "MTF aligned" in out["why"]


@pytest.mark.unit
def test_execution_trace_exposes_blocker_metrics() -> None:
    trace = build_institutional_execution_trace(
        symbol="XAUUSD",
        decision_id="dec_1",
        ai_score={
            "reject": True,
            "reject_reason": "valid_volatility",
            "trade_quality": 72,
            "ai_confidence": 70,
            "direction": "NONE",
            "liquidity": 55,
            "volatility_decision": {"passed": False, "reason": "ATR% below hard min"},
            "factors": {"mtf": 40, "bos": 20},
        },
        scanner={"best_symbol": None, "eligible_count": 0, "universe": ["XAUUSD"]},
        market_ok=True,
    )
    assert trace["observe_only"] is True
    names = [s["stage"] for s in trace["stages"]]
    assert names[0] == "Market Data"
    assert "Volatility" in names
    assert "Quality" in names
    assert "OMS" in names
    vol = next(s for s in trace["stages"] if s["stage"] == "Volatility")
    assert vol["status"] == "FAIL"
    assert vol["decision_id"] == "dec_1"
    assert vol["symbol"] == "XAUUSD"


@pytest.mark.unit
def test_calendar_adapter_filters_high_impact_window() -> None:
    now = datetime.now(UTC)
    feed = SimpleNamespace(
        list_events=lambda **_: [
            SimpleNamespace(
                id="1",
                title="FOMC Rate Decision",
                scheduled_at=(now + timedelta(minutes=5)).isoformat(),
                impact="high",
            ),
            SimpleNamespace(
                id="2",
                title="Low impact fluff",
                scheduled_at=(now + timedelta(hours=5)).isoformat(),
                impact="low",
            ),
        ]
    )
    adapter = EconomicCalendarNewsAdapter(feed=feed)
    hits = adapter.events_near(as_of=now, minutes_before=0, minutes_after=30)
    assert len(hits) == 1
    assert hits[0].code == "FOMC"
    assert hits[0].impact == "high"


@pytest.mark.unit
def test_spread_abnormal_vs_history_rejects() -> None:
    # Seed a tight history then spike
    for _ in range(10):
        assess_spread(Decimal("0.20"), atr=Decimal("5"), symbol="EURUSD_TEST")
    spiked = assess_spread(Decimal("1.50"), atr=Decimal("5"), symbol="EURUSD_TEST")
    assert spiked.reject is True
    assert spiked.abnormal_vs_history is True


@pytest.mark.unit
def test_continuous_pause_covers_emergency_triggers() -> None:
    ctrl = ContinuousOperationController()
    d = ctrl.evaluate_new_entry_pause(
        margin_danger=True,
        abnormal_spread=True,
        flash_crash=True,
        network_failure=True,
        mt5_connected=False,
    )
    assert d.pause_new_entries is True
    assert d.manage_open_positions is True
    joined = " ".join(d.reasons).lower()
    assert "margin" in joined
    assert "spread" in joined
    assert "flash" in joined
    assert "network" in joined
    assert "mt5" in joined
