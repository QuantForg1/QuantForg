"""Evaluate all strategy profiles against one symbol score (SCALPING_V1 floors)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.strategies.models import (
    StrategyDefinition,
    StrategyEvaluation,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    ALL_STRATEGIES,
)


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _components(score: dict[str, Any]) -> tuple[dict[str, int], str, str, str]:
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    vol = (
        score.get("volatility_decision")
        if isinstance(score.get("volatility_decision"), dict)
        else {}
    )
    atr_band = "normal"
    thresholds = score.get("thresholds") if isinstance(score.get("thresholds"), dict) else {}
    if thresholds.get("band"):
        atr_band = str(thresholds.get("band"))
    elif vol.get("band"):
        atr_band = str(vol.get("band"))
    bos_raw = _i(factors.get("bos"))
    comps = {
        "quality": _i(score.get("trade_quality") or score.get("quality")),
        "confidence": _i(score.get("ai_confidence") or score.get("confidence")),
        "structure": _i(
            score.get("structure_score") or factors.get("bos") or factors.get("choch")
        ),
        "momentum": _i(score.get("momentum") or factors.get("momentum")),
        "liquidity": _i(score.get("liquidity") or factors.get("liquidity_sweep")),
        "mtf": _i(score.get("mtf_alignment") or factors.get("mtf") or factors.get("h1_bias")),
        "order_block": _i(factors.get("order_block")),
        "fvg": _i(factors.get("fvg")),
        "volume": _i(factors.get("volume")),
        "volatility": _i(factors.get("volatility") or factors.get("atr_expansion") or 50),
        "ema": _i(factors.get("ema")),
        "trend_strength": _i(factors.get("trend_strength") or factors.get("momentum")),
        "pa_confluence": _i(factors.get("pa_confluence")),
        "spread": _i(score.get("spread_score") or factors.get("spread") or 50),
        "bos": 1 if bos_raw >= 50 else 0,
    }
    regime = str(score.get("market_regime") or score.get("regime") or "")
    setup_family = str(score.get("setup_family") or "")
    return comps, atr_band, regime, setup_family


def _weighted_score(components: dict[str, int], weights: dict[str, float]) -> int:
    total_w = 0.0
    acc = 0.0
    for key, w in weights.items():
        total_w += float(w)
        acc += float(w) * float(components.get(key, 0))
    if total_w <= 0:
        return 0
    return max(0, min(100, int(round(acc / total_w))))


def evaluate_strategy(
    score: dict[str, Any],
    strategy: StrategyDefinition,
    *,
    config: AiScalpingConfig | None = None,
    live_rank_boost: float = 0.0,
) -> StrategyEvaluation:
    """Score one strategy. Hard base reject still blocks; soft floors do not."""
    _ = config
    symbol = str(score.get("symbol") or "").upper()
    direction = str(score.get("direction") or "NONE").upper()
    comps, atr_band, regime, setup_fam = _components(score)
    filters: dict[str, bool] = {}
    reasons: list[str] = []

    base_reject = bool(score.get("reject"))
    filters["base_gates_clear"] = not base_reject
    if base_reject:
        reasons.append(
            f"Base SCALPING_V1 gates reject: {score.get('reject_reason') or 'reject'}"
        )

    # Floors are Probability Center evidence — no independent AND-kill.
    filters["structure_floor"] = True
    filters["momentum_floor"] = True

    if strategy.require_regimes:
        ok = regime in strategy.require_regimes
        filters["regime_required"] = ok
        if not ok:
            reasons.append(
                f"Regime {regime or 'unknown'} not in {strategy.require_regimes}"
            )
    if strategy.forbid_regimes:
        ok = regime not in strategy.forbid_regimes
        filters["regime_allowed"] = ok
        if not ok:
            reasons.append(f"Regime {regime} forbidden for {strategy.strategy_id}")

    if strategy.min_alignment:
        ok = comps["mtf"] >= int(strategy.min_alignment)
        filters["alignment"] = ok
        if not ok:
            reasons.append(f"MTF {comps['mtf']} < {strategy.min_alignment}")

    if strategy.min_bos:
        ok = comps["bos"] >= 1
        filters["bos"] = ok
        if not ok:
            reasons.append("BOS evidence required for breakout/continuation")

    if strategy.min_volume:
        ok = comps["volume"] >= int(strategy.min_volume)
        filters["volume"] = ok
        if not ok:
            reasons.append(f"Volume {comps['volume']} < {strategy.min_volume}")

    if strategy.require_atr_band:
        ok = atr_band in strategy.require_atr_band
        filters["atr_band"] = ok
        if not ok:
            reasons.append(f"ATR band {atr_band} not in {strategy.require_atr_band}")

    strategy_quality = _weighted_score(comps, strategy.weights)
    base_conf = comps["confidence"]
    strategy_confidence = max(
        0,
        min(100, int(round(0.55 * base_conf + 0.45 * strategy_quality))),
    )

    if strategy.prefer_setup_families and setup_fam in strategy.prefer_setup_families:
        strategy_quality = min(100, strategy_quality + 3)
        reasons.append(f"Setup family {setup_fam} fits {strategy.name}")

    filters["strategy_quality_floor"] = True
    filters["strategy_confidence_floor"] = True

    direction_ok = direction in {"BUY", "SELL"}
    filters["clear_direction"] = direction_ok
    if not direction_ok:
        reasons.append("No clear BUY/SELL direction")

    passed = all(filters.values()) and not base_reject and direction_ok
    explanation = (
        f"{strategy.name}: {strategy.explanation} | "
        + ("; ".join(reasons) if reasons else "all strategy filters cleared")
    )
    reject_reason = None if passed else ("; ".join(reasons) or "strategy_reject")

    return StrategyEvaluation(
        strategy_id=strategy.strategy_id,
        name=strategy.name,
        symbol=symbol,
        direction=direction if passed else "NONE",
        passed=passed,
        quality=strategy_quality,
        confidence=strategy_confidence,
        explanation=explanation,
        reject_reason=reject_reason,
        filters=filters,
        score_components=comps,
        live_rank_boost=float(live_rank_boost),
    )


def evaluate_all_strategies(
    score: dict[str, Any],
    *,
    config: AiScalpingConfig | None = None,
    live_boosts: dict[str, float] | None = None,
) -> tuple[StrategyEvaluation, ...]:
    boosts = live_boosts or {}
    return tuple(
        evaluate_strategy(
            score,
            strat,
            config=config,
            live_rank_boost=float(boosts.get(strat.strategy_id, 0.0)),
        )
        for strat in ALL_STRATEGIES
    )
