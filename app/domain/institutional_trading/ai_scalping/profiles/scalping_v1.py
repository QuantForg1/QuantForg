"""SCALPING_V1 — Professional AI Scalping Engine production profile.

Intentional product change: QuantForg production default is professional
scalping (not institutional swing gates). Reuses AiScalpingConfig + PME
mapping — does not rewrite OMS / Risk / Gateway / MT5 / database.

All quality gates that previously fell through to institutional class
defaults are owned here so the profile is internally consistent.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    AdaptiveThresholdBand,
    AiScalpingConfig,
)

PROFILE_ID = "SCALPING_V1"
PROFILE_VERSION = "ai-scalping-v8.2.0+SCALPING_V1+UNIVERSE_GATE_FIX"

# Professional scalping RR target — min gate MUST match (never demand more).
_SCALP_RR = Decimal("1.20")


def build_scalping_v1_config(base: AiScalpingConfig | None = None) -> AiScalpingConfig:
    """Professional LIVE scalping knobs — fully profile-owned gates."""
    src = base or AiScalpingConfig()
    return replace(
        src,
        version=PROFILE_VERSION,
        quality_baseline=PROFILE_ID,
        continuous_version="ai-scalping-v7.1.0+SCALPING_V1",
        trading_mode="scalping",
        # Adaptive quality / confluence bands (professional scalping)
        high_vol=AdaptiveThresholdBand(quality=72, confidence=70),
        normal_vol=AdaptiveThresholdBand(quality=74, confidence=71),
        low_vol=AdaptiveThresholdBand(quality=75, confidence=72),
        # --- Profile-owned gates (were institutional class leftovers) ---
        # Structure / momentum / liquidity / PA: scalping-calibrated floors.
        # Still hard gates (not disabled). Not institutional swing 70/65/60/50.
        # Require real structure & confirmation — reject noise / dead tape.
        min_structure_score=60,
        min_momentum_score=55,
        min_liquidity_score=55,
        min_pa_confluence_score=45,
        setup_min_local_score=55,
        direction_edge_margin=5,
        require_strong_structure=True,
        require_momentum_confirm=True,
        require_liquidity_event=True,
        require_pa_confluence=True,
        require_tight_spread=True,
        require_valid_volatility=True,
        # RR MUST equal fixed TP — institutional min 1.3 + regime bumps → 1.4
        # contradicted fixed_tp_r=1.20 (LIVE: Expected RR 1.20 below minimum 1.4).
        min_expected_rr=_SCALP_RR,
        fixed_tp_r=_SCALP_RR,
        atr_tp_mult=Decimal("1.40"),
        # Hold window: target 2–10m, absolute 12m
        typical_hold_min_minutes=2,
        typical_hold_max_minutes=10,
        max_hold_minutes_if_confident=10,
        high_confidence_for_extend=78,
        absolute_max_hold_minutes=12,
        time_stop_minutes=8,
        time_stop_min_r=Decimal("0.25"),
        # Faster adaptive cooldown — continuous recycling
        cooldown_min_seconds=20,
        cooldown_base_seconds=45,
        cooldown_max_seconds=180,
        # Multi independent opportunities (not one-best only)
        max_open_trades=5,
        max_entries_per_cycle=5,
        require_probability_improvement=False,
        min_confidence_delta_for_add=0,
        parallel_scan_enabled=True,
        parallel_scan_concurrency=4,
        post_close_rescan_enabled=True,
        post_close_rescan_delay_seconds=0.0,
        continuous_operation_enabled=True,
        multi_asset_scan_enabled=True,
        # Dynamic liquid universe from LIVE broker catalogue (gates unchanged)
        dynamic_universe_enabled=True,
        max_universe_symbols=36,
        session_symbol_priority_enabled=True,
        live_symbol_learning_enabled=True,
        multi_strategy_enabled=True,
        # PME — earlier BE / partial / trail (do not increase losses)
        break_even_at_r=Decimal("0.35"),
        partial_at_r=Decimal("0.70"),
        partial_close_pct=Decimal("50"),
        trail_after_r=Decimal("0.70"),
        momentum_fade_exit=True,
        momentum_fade_threshold=45,
        volatility_collapse_exit=True,
        volatility_collapse_threshold=30,
        # Safety locked
        allow_martingale=False,
        allow_grid=False,
        self_protection_enabled=True,
        news_protection_enabled=True,
    )


SCALPING_V1: AiScalpingConfig = build_scalping_v1_config()
