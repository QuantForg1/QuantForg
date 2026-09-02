"""SCALPING_V1 — Professional AI Scalping Engine production profile tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.ai_scalping_mode import pme_config_for_scalping
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.profiles import (
    ACTIVE_PRODUCTION_PROFILE,
    SCALPING_V1,
    SCALPING_V1_ID,
)
from app.domain.institutional_trading.ai_scalping.regime import RegimeAssessment
from app.domain.institutional_trading.ai_scalping.regime_execution import (
    build_regime_execution_profile,
)
from app.domain.institutional_trading.management.config import DEFAULT_PME_CONFIG


@pytest.mark.unit
def test_scalping_v1_is_production_default() -> None:
    assert ACTIVE_PRODUCTION_PROFILE == SCALPING_V1_ID
    assert DEFAULT_AI_SCALPING_CONFIG.quality_baseline == SCALPING_V1_ID
    assert DEFAULT_AI_SCALPING_CONFIG.version == SCALPING_V1.version


@pytest.mark.unit
def test_scalping_v1_adaptive_quality_confluence_bands() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.high_vol.quality == 72
    assert cfg.high_vol.confidence == 70
    assert cfg.normal_vol.quality == 74
    assert cfg.normal_vol.confidence == 71
    assert cfg.low_vol.quality == 75
    assert cfg.low_vol.confidence == 72
    assert 72 <= cfg.high_vol.quality <= 75
    assert 70 <= cfg.high_vol.confidence <= 72


@pytest.mark.unit
def test_scalping_v1_hold_window() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.typical_hold_min_minutes == 2
    assert cfg.typical_hold_max_minutes == 10
    assert cfg.absolute_max_hold_minutes == 12
    assert cfg.time_stop_minutes == 8


@pytest.mark.unit
def test_scalping_v1_gates_are_profile_owned_not_institutional() -> None:
    """Structure/momentum/RR/PA must not silently inherit institutional leftovers."""
    cfg = DEFAULT_AI_SCALPING_CONFIG
    institutional = AiScalpingConfig()  # bare class = research institutional
    assert cfg.min_structure_score == 60
    assert cfg.min_momentum_score == 55
    assert cfg.min_liquidity_score == 55
    assert cfg.min_pa_confluence_score == 45
    assert cfg.min_structure_score < institutional.min_structure_score
    assert cfg.min_momentum_score < institutional.min_momentum_score
    # Still hard gates — not disabled
    assert cfg.require_strong_structure is True
    assert cfg.require_momentum_confirm is True
    assert cfg.require_liquidity_event is True
    assert cfg.require_pa_confluence is True


@pytest.mark.unit
def test_scalping_v1_rr_internally_consistent() -> None:
    """fixed_tp_r and min_expected_rr must never contradict."""
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.fixed_tp_r == Decimal("1.20")
    assert cfg.min_expected_rr == Decimal("1.20")
    assert cfg.min_expected_rr <= cfg.fixed_tp_r
    # Regime bumps must not push RR above fixed TP
    for regime in ("range", "compression", "expansion", "strong_trend"):
        assessment = RegimeAssessment(
            regime=regime,  # type: ignore[arg-type]
            confidence=70,
            reasons=(f"test-{regime}",),
        )
        profile = build_regime_execution_profile(
            assessment, atr_pct=Decimal("0.50"), config=cfg
        )
        assert profile.min_expected_rr <= cfg.fixed_tp_r
        assert profile.min_expected_rr >= cfg.min_expected_rr


@pytest.mark.unit
def test_config_post_init_clamps_rr_to_fixed_tp() -> None:
    """Even a misconfigured profile cannot demand RR above fixed TP."""
    broken = AiScalpingConfig(
        fixed_tp_r=Decimal("1.20"),
        min_expected_rr=Decimal("1.40"),
    )
    assert broken.min_expected_rr == Decimal("1.20")


@pytest.mark.unit
def test_scalping_v1_multi_opportunity_not_one_best_only() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.max_entries_per_cycle >= 3
    assert cfg.max_open_trades >= 3
    assert cfg.require_probability_improvement is False
    assert cfg.parallel_scan_enabled is True
    assert cfg.multi_asset_scan_enabled is True


@pytest.mark.unit
def test_scalping_v1_pme_earlier_management() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    pme = pme_config_for_scalping(cfg)
    assert pme.break_even_at_r == Decimal("0.80")
    assert pme.partial_at_r == Decimal("1.20")
    assert pme.trail_after_r == Decimal("1.20")
    assert pme.absolute_max_hold_minutes == 12
    assert pme.time_stop_minutes == 8
    assert pme.momentum_fade_exit is True
    assert pme.break_even_at_r < DEFAULT_PME_CONFIG.break_even_at_r
    assert pme.partial_at_r < DEFAULT_PME_CONFIG.partial_at_r


@pytest.mark.unit
def test_scalping_v1_safety_locked() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.never_prefer_buy_only is True
    assert cfg.self_protection_enabled is True


@pytest.mark.unit
def test_scalping_ite_maps_v1_floors() -> None:
    ite = scalping_ite_config()
    assert ite.trading_mode == "scalping"
    assert ite.min_trade_quality_score == 74
    assert ite.min_confluence_score == 71
    assert ite.max_open_trades >= 3
