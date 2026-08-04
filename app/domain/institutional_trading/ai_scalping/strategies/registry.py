"""Production strategy registry — five independent scalping strategies."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyDefinition,
    StrategyId,
)

SMC_SCALPING = StrategyDefinition(
    strategy_id="smc_scalping",
    name="SMC Scalping",
    explanation=(
        "SCALPING_V1 institutional SMC path — structure, order blocks, FVG, "
        "liquidity sweeps. Production baseline; floors never lowered."
    ),
    weights={
        "structure": 22,
        "order_block": 16,
        "fvg": 14,
        "liquidity": 14,
        "mtf": 12,
        "momentum": 10,
        "quality": 12,
    },
    prefer_setup_families=(
        "bos_continuation",
        "choch_reversal",
        "liquidity_sweep_reversal",
        "fvg_continuation",
    ),
)

TREND_CONTINUATION = StrategyDefinition(
    strategy_id="trend_continuation",
    name="Trend Continuation Scalping",
    explanation=(
        "Pullback continuation in aligned trends — MTF alignment + BOS + EMA lean. "
        "Requires stronger alignment than baseline (stricter, not weaker)."
    ),
    weights={
        "mtf": 24,
        "structure": 16,
        "momentum": 16,
        "ema": 14,
        "trend_strength": 12,
        "quality": 10,
        "liquidity": 8,
    },
    min_alignment=70,  # stricter than noise
    prefer_setup_families=("pullback_continuation", "bos_continuation"),
    forbid_regimes=("range", "compression"),
)

BREAKOUT_SCALPING = StrategyDefinition(
    strategy_id="breakout_scalping",
    name="Breakout Scalping",
    explanation=(
        "Volatility expansion breakouts — BOS + volume + ATR expansion band. "
        "Requires high/normal ATR band (stricter)."
    ),
    weights={
        "structure": 18,
        "volume": 18,
        "volatility": 18,
        "momentum": 14,
        "mtf": 12,
        "quality": 12,
        "liquidity": 8,
    },
    min_bos=1,
    min_volume=60,
    require_atr_band=("high", "normal"),
    prefer_setup_families=("breakout_continuation", "bos_continuation"),
    forbid_regimes=("compression",),
)

RANGE_MEAN_REVERSION = StrategyDefinition(
    strategy_id="range_mean_reversion",
    name="Range Mean-Reversion Scalping",
    explanation=(
        "Fade extremes in range/compression — liquidity sweep + CHOCH mean revert. "
        "Only active in range-like regimes (specialized, not looser)."
    ),
    weights={
        "liquidity": 22,
        "structure": 16,
        "momentum": 10,
        "pa_confluence": 14,
        "spread": 12,
        "quality": 14,
        "fvg": 12,
    },
    require_regimes=("range", "compression"),
    prefer_setup_families=("liquidity_sweep_reversal", "choch_reversal"),
)

MOMENTUM_SCALPING = StrategyDefinition(
    strategy_id="momentum_scalping",
    name="Momentum Scalping",
    explanation=(
        "Directional momentum confirmation — strong momentum + trend strength. "
        "Requires momentum above SCALPING_V1 floor (never below)."
    ),
    weights={
        "momentum": 28,
        "trend_strength": 18,
        "mtf": 14,
        "volume": 12,
        "quality": 14,
        "structure": 14,
    },
    min_momentum=65,  # stricter than SCALPING_V1 55
    prefer_setup_families=("pullback_continuation", "breakout_continuation"),
    forbid_regimes=("compression",),
)

ALL_STRATEGIES: tuple[StrategyDefinition, ...] = (
    SMC_SCALPING,
    TREND_CONTINUATION,
    BREAKOUT_SCALPING,
    RANGE_MEAN_REVERSION,
    MOMENTUM_SCALPING,
)

STRATEGY_BY_ID: dict[StrategyId, StrategyDefinition] = {
    s.strategy_id: s for s in ALL_STRATEGIES
}


def list_strategy_ids() -> tuple[StrategyId, ...]:
    return tuple(s.strategy_id for s in ALL_STRATEGIES)
