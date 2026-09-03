"""Global market intelligence + loss-streak adaptation unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_scalping.global_market_intelligence import (
    assess_global_market_intelligence,
)
from app.domain.institutional_trading.ai_scalping.loss_streak_adaptation import (
    MODE_DEFENSIVE,
    MODE_NORMAL,
    MODE_TIGHTENED,
    cooldown_until_after_streak,
    resolve_loss_streak_adaptation,
)
from app.domain.institutional_trading.live_trading_control import LiveTradingController


@pytest.mark.unit
@pytest.mark.trading_core
def test_intelligence_marks_unavailable_sources() -> None:
    gmi = assess_global_market_intelligence(
        direction="BUY",
        structure_score=80,
        momentum=75,
        liquidity=70,
        expected_rr=1.5,
        market_regime="strong_trend",
        atr_band="normal",
        news_blocked=False,
        mtf_alignment=80,
    )
    assert gmi.intelligence_alignment in {
        "STRONGLY_ALIGNED",
        "ALIGNED",
        "NEUTRAL",
        "UNKNOWN",
    }
    assert any(s.status == "SOURCE_UNAVAILABLE" for s in gmi.sources)
    assert gmi.wait_recommended is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_intelligence_event_risk_waits() -> None:
    gmi = assess_global_market_intelligence(
        direction="BUY",
        structure_score=90,
        momentum=90,
        liquidity=90,
        expected_rr=2.0,
        news_blocked=True,
        news_reason="High-impact news blackout: NFP",
        mtf_alignment=90,
    )
    assert gmi.global_regime == "EVENT_RISK"
    assert gmi.intelligence_alignment == "HIGH_RISK"
    assert gmi.wait_recommended is True
    assert gmi.wait_code == "WAIT_EVENT_RISK"


@pytest.mark.unit
@pytest.mark.trading_core
def test_intelligence_conflict_waits_on_execution_degradation() -> None:
    """Hard WAIT only on affirmative degraded evidence — not weak MTF/structure."""
    gmi = assess_global_market_intelligence(
        direction="BUY",
        structure_score=85,
        momentum=80,
        liquidity=80,
        expected_rr=1.4,
        mtf_alignment=80,
        news_blocked=False,
        execution_quality_ok=False,
    )
    assert gmi.intelligence_alignment == "CONFLICTED"
    assert gmi.wait_recommended is True
    assert gmi.wait_code == "WAIT_INTELLIGENCE_CONFLICT"


@pytest.mark.unit
@pytest.mark.trading_core
def test_mtf_zero_is_unknown_not_conflict() -> None:
    """MTF alignment 0 must be UNKNOWN, not WAIT_INTELLIGENCE_CONFLICT."""
    gmi = assess_global_market_intelligence(
        direction="SELL",
        structure_score=85,
        momentum=0,
        liquidity=70,
        expected_rr=1.82,
        mtf_alignment=0,
        news_blocked=False,
        execution_quality_ok=True,
    )
    cross = next(layer for layer in gmi.layers if layer.name == "cross_asset")
    assert cross.state == "UNKNOWN"
    assert gmi.wait_recommended is False
    assert gmi.wait_code is None
    assert "conflicts with" not in cross.reason.lower()


@pytest.mark.unit
@pytest.mark.trading_core
def test_weak_mtf_is_not_directional_conflict() -> None:
    gmi = assess_global_market_intelligence(
        direction="BUY",
        structure_score=20,
        momentum=20,
        liquidity=80,
        expected_rr=1.4,
        mtf_alignment=20,
        news_blocked=False,
    )
    cross = next(layer for layer in gmi.layers if layer.name == "cross_asset")
    assert cross.state == "UNKNOWN"
    assert gmi.wait_recommended is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_unknown_is_not_confirmation() -> None:
    gmi = assess_global_market_intelligence(direction=None)
    assert gmi.intelligence_alignment in {"UNKNOWN", "NEUTRAL"}
    assert gmi.wait_recommended is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_loss_streak_modes() -> None:
    assert resolve_loss_streak_adaptation(consecutive_losses=1).mode == MODE_NORMAL
    assert resolve_loss_streak_adaptation(consecutive_losses=3).mode == MODE_TIGHTENED
    assert resolve_loss_streak_adaptation(consecutive_losses=4).mode == MODE_DEFENSIVE
    defensive = resolve_loss_streak_adaptation(consecutive_losses=5)
    assert defensive.require_stronger_selection is True
    assert defensive.min_expected_rr_soft >= 1.35
    assert defensive.to_dict()["allow_martingale"] is False
    assert defensive.to_dict()["permanent_disable"] is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_loss_streak_cooldown_is_time_boxed() -> None:
    now = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    until = cooldown_until_after_streak(
        consecutive_losses=3,
        max_consecutive_losses=3,
        cooldown_minutes=60,
        now=now,
    )
    assert until == now + timedelta(minutes=60)
    active = resolve_loss_streak_adaptation(
        consecutive_losses=3, cooldown_until=until, now=now
    )
    assert active.cooldown_active is True
    expired = resolve_loss_streak_adaptation(
        consecutive_losses=3,
        cooldown_until=until,
        now=now + timedelta(minutes=61),
    )
    assert expired.cooldown_active is False
    assert expired.mode == MODE_TIGHTENED


@pytest.mark.unit
@pytest.mark.trading_core
def test_controller_notes_closed_trade_and_recovers() -> None:
    ctrl = LiveTradingController()
    ctrl.note_closed_trade(loss=True, volume=Decimal("0.01"))
    ctrl.note_closed_trade(loss=True, volume=Decimal("0.01"))
    ctrl.note_closed_trade(loss=True, volume=Decimal("0.01"))
    assert ctrl.consecutive_losses == 3
    assert ctrl.loss_streak_cooldown_active() is True
    snap = ctrl.loss_streak_snapshot()
    assert snap["cooldown_active"] is True
    # Simulate cooldown expiry
    ctrl.loss_streak_cooldown_until = datetime.now(UTC) - timedelta(minutes=1)
    assert ctrl.loss_streak_cooldown_active() is False
    # Win resets streak — robot continues
    ctrl.note_closed_trade(loss=False, volume=Decimal("0.01"))
    assert ctrl.consecutive_losses == 0
    assert ctrl.loss_streak_cooldown_until is None
