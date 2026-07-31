"""Unit tests — Institutional AI Scalping v6.3 adaptive mode."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.ai_scalping_mode import pme_config_for_scalping
from app.domain.institutional_trading.ai_scalping.adaptive_cooldown import (
    AdaptiveCooldownGate,
    get_adaptive_cooldown_gate,
    resolve_adaptive_cooldown_seconds,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.regime import classify_scalping_regime
from app.domain.institutional_trading.ai_scalping.regime_execution import (
    build_regime_execution_profile,
)
from app.domain.institutional_trading.ai_scalping.setup_scanner import (
    scan_setup_families,
)
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.policies import plan_action


@pytest.mark.unit
def test_v63_version_preserves_quality_and_risk() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.quality_baseline == "ai-scalping-v6.3.0"
    assert cfg.version.startswith("ai-scalping-v8")
    assert cfg.risk_per_trade_pct <= Decimal("0.75")
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.min_expected_rr >= Decimal("1.3")
    assert cfg.typical_hold_min_minutes == 2
    assert cfg.typical_hold_max_minutes == 15
    assert cfg.absolute_max_hold_minutes >= cfg.typical_hold_max_minutes
    assert cfg.normal_vol.confidence == 82
    assert cfg.normal_vol.quality == 82


@pytest.mark.unit
def test_regimes_cover_adaptive_taxonomy() -> None:
    labels = {
        classify_scalping_regime(
            alignment_score=80, bos=1, atr_pct=Decimal("0.8")
        ).regime,
        classify_scalping_regime(alignment_score=60, atr_pct=Decimal("0.8")).regime,
        classify_scalping_regime(
            alignment_score=40, range_like=True, atr_pct=Decimal("0.8")
        ).regime,
        classify_scalping_regime(
            alignment_score=70,
            bos=1,
            volume_expanding=True,
            atr_pct=Decimal("2.0"),
        ).regime,
        classify_scalping_regime(alignment_score=55, atr_pct=Decimal("2.0")).regime,
        classify_scalping_regime(
            alignment_score=40, range_like=True, atr_pct=Decimal("0.2")
        ).regime,
    }
    assert "strong_trend" in labels
    assert "weak_trend" in labels
    assert "range" in labels
    assert "breakout" in labels
    assert "expansion" in labels
    assert "compression" in labels


@pytest.mark.unit
def test_regime_profile_never_lowers_rr_or_past_max() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    for regime_fn in (
        lambda: classify_scalping_regime(
            alignment_score=80, bos=1, atr_pct=Decimal("2.0"), volume_expanding=True
        ),
        lambda: classify_scalping_regime(
            alignment_score=40, atr_pct=Decimal("0.2"), range_like=True
        ),
        lambda: classify_scalping_regime(alignment_score=60, atr_pct=Decimal("0.9")),
    ):
        assessment = regime_fn()
        profile = build_regime_execution_profile(
            assessment, atr_pct=Decimal("1.0"), config=cfg
        )
        assert profile.min_expected_rr >= cfg.min_expected_rr
        assert profile.absolute_max_hold_minutes <= cfg.absolute_max_hold_minutes
        assert profile.target_hold_max_minutes <= cfg.typical_hold_max_minutes
        assert profile.target_hold_min_minutes >= cfg.typical_hold_min_minutes


@pytest.mark.unit
def test_setup_scan_failed_family_does_not_poison_others() -> None:
    scan = scan_setup_families(
        alignment=80,
        bos=1,
        choch=0,
        sweeps=0,
        open_fvg=0,
        momentum=70,
        volume=80,
        liquidity=40,
        ema=70,
        buy_score=75,
        sell_score=30,
        atr_band="high",
    )
    assert any(
        c.family == "liquidity_sweep_reversal" and not c.passed for c in scan.candidates
    )
    assert scan.best is not None
    assert scan.best.passed is True
    assert scan.best.family in {
        "bos_continuation",
        "breakout_continuation",
        "pullback_continuation",
    }


@pytest.mark.unit
def test_setup_scan_selects_highest_score_only() -> None:
    scan = scan_setup_families(
        alignment=85,
        bos=2,
        choch=1,
        sweeps=2,
        open_fvg=1,
        momentum=75,
        volume=85,
        liquidity=90,
        ema=80,
        buy_score=80,
        sell_score=40,
        atr_band="high",
    )
    passed = [c for c in scan.candidates if c.passed]
    assert len(passed) >= 2
    assert scan.best is not None
    assert scan.best.score == max(c.score for c in passed)


@pytest.mark.unit
def test_adaptive_cooldown_shorter_in_good_conditions() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    good = resolve_adaptive_cooldown_seconds(
        atr_pct=Decimal("0.9"),
        spread_score=90,
        liquidity_score=90,
        execution_quality_ok=True,
        recent_rejects=0,
        regime="strong_trend",
        config=cfg,
    )
    poor = resolve_adaptive_cooldown_seconds(
        atr_pct=Decimal("2.5"),
        spread_score=40,
        liquidity_score=40,
        execution_quality_ok=False,
        recent_rejects=4,
        regime="compression",
        config=cfg,
    )
    assert good.seconds >= cfg.cooldown_min_seconds
    assert poor.seconds > good.seconds
    assert poor.seconds <= cfg.cooldown_max_seconds


@pytest.mark.unit
def test_adaptive_cooldown_gate_blocks_then_clears() -> None:
    gate = AdaptiveCooldownGate()
    decision = resolve_adaptive_cooldown_seconds(
        atr_pct=Decimal("0.9"),
        spread_score=80,
        liquidity_score=80,
        regime="strong_trend",
    )
    gate.note_entry(seconds=2)
    blocked = gate.evaluate(decision)
    assert blocked.allow_new_entry is False
    assert blocked.remaining_seconds > 0
    gate.reset()
    clear = gate.evaluate(decision)
    assert clear.allow_new_entry is True


@pytest.mark.unit
def test_volatility_collapse_exit() -> None:
    pme = pme_config_for_scalping()
    assert pme.volatility_collapse_exit is True
    pos = ManagedPosition(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("2300"),
        initial_volume=Decimal("0.10"),
        remaining_volume=Decimal("0.10"),
        initial_stop=Decimal("2295"),
        risk_distance=Decimal("5"),
        opened_at=datetime.now(UTC) - timedelta(minutes=3),
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("2295"),
    )
    ctx = PositionManageContext(
        now=datetime.now(UTC),
        current_price=Decimal("2301"),
        atr=Decimal("2"),
        mid_price=Decimal("2301"),
        ai_volatility=10,
        ai_momentum=60,
    )
    action = plan_action(pos, ctx, pme)
    assert action.kind is ManageActionKind.EMERGENCY_EXIT
    assert "Volatility collapsed" in action.reason


@pytest.mark.unit
def test_global_cooldown_gate_reset_isolation() -> None:
    get_adaptive_cooldown_gate().reset()
    d = resolve_adaptive_cooldown_seconds(regime="range")
    assert get_adaptive_cooldown_gate().evaluate(d).allow_new_entry is True
