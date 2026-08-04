"""Multi-strategy scalping pack unit tests — floors never lowered."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.strategies import (
    ALL_STRATEGIES,
    attach_strategies_to_scores,
    best_strategy_for_symbol,
    evaluate_all_strategies,
    evaluate_strategy,
    get_strategy_stats_book,
    list_strategy_ids,
    select_global_best,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    MOMENTUM_SCALPING,
    RANGE_MEAN_REVERSION,
    SMC_SCALPING,
)
from app.domain.institutional_trading.ai_scalping.strategies.stats import (
    StrategyStatsBook,
)


def _base_score(**overrides):
    row = {
        "symbol": "XAUUSD",
        "reject": False,
        "direction": "SELL",
        "trade_quality": 80,
        "ai_confidence": 78,
        "structure_score": 72,
        "momentum": 70,
        "liquidity": 70,
        "mtf_alignment": 75,
        "spread_score": 70,
        "market_regime": "strong_trend",
        "setup_family": "bos_continuation",
        "thresholds": {"quality": 74, "confidence": 71, "band": "normal"},
        "factors": {
            "bos": 85,
            "choch": 20,
            "order_block": 80,
            "fvg": 70,
            "momentum": 70,
            "volume": 75,
            "volatility": 70,
            "atr_expansion": 70,
            "ema": 70,
            "trend_strength": 75,
            "pa_confluence": 60,
            "liquidity_sweep": 70,
            "mtf": 75,
            "spread": 70,
        },
    }
    row.update(overrides)
    return row


@pytest.mark.unit
def test_five_strategies_registered() -> None:
    ids = list_strategy_ids()
    assert len(ids) == 5
    assert "smc_scalping" in ids
    assert len(ALL_STRATEGIES) == 5


@pytest.mark.unit
def test_strategies_never_below_scalping_v1_floors() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.min_structure_score == 60
    assert cfg.min_momentum_score == 55
    assert cfg.normal_vol.quality == 74
    assert cfg.multi_strategy_enabled is True
    # Momentum strategy is stricter, not weaker
    assert MOMENTUM_SCALPING.min_momentum >= cfg.min_momentum_score


@pytest.mark.unit
def test_base_reject_blocks_all_strategies() -> None:
    score = _base_score(reject=True, reject_reason="Weak structure", direction="NONE")
    evals = evaluate_all_strategies(score)
    assert len(evals) == 5
    assert all(not e.passed for e in evals)
    assert best_strategy_for_symbol(evals) is None


@pytest.mark.unit
def test_smc_can_pass_on_strong_setup() -> None:
    score = _base_score()
    ev = evaluate_strategy(score, SMC_SCALPING)
    assert ev.passed is True
    assert ev.strategy_id == "smc_scalping"
    assert ev.quality >= 74
    assert ev.direction == "SELL"
    assert "SMC" in ev.explanation


@pytest.mark.unit
def test_range_strategy_rejects_strong_trend_regime() -> None:
    score = _base_score(market_regime="strong_trend")
    ev = evaluate_strategy(score, RANGE_MEAN_REVERSION)
    assert ev.passed is False
    assert "Regime" in (ev.reject_reason or "")


@pytest.mark.unit
def test_one_strategy_per_symbol_then_global_best() -> None:
    score = _base_score()
    evals = evaluate_all_strategies(score)
    best = best_strategy_for_symbol(evals)
    assert best is not None
    # Only one winner per symbol
    winners = [best]
    scored, global_best, per_sym = attach_strategies_to_scores(
        [score], evaluations_by_symbol={"XAUUSD": evals}
    )
    assert len(per_sym) == 1
    assert scored[0]["strategy_id"] == per_sym[0].strategy_id
    assert global_best is not None
    assert select_global_best(winners).strategy_id == best.strategy_id


@pytest.mark.unit
def test_strategy_stats_and_live_rank(tmp_path: Path) -> None:
    book = StrategyStatsBook(_path=tmp_path / "strat_stats.json")
    book.record_evaluation("smc_scalping", passed=True)
    book.record_evaluation("smc_scalping", passed=False)
    book.record_accepted("smc_scalping", latency_ms=400.0)
    book.record_closed("smc_scalping", win=True, pnl=10.0, hold_minutes=5.0, r_multiple=1.2)
    book.record_closed("smc_scalping", win=False, pnl=-4.0, hold_minutes=3.0, r_multiple=-1.0)
    snap = book.snapshot()
    assert "smc_scalping" in book.live_rank_boosts()
    row = next(r for r in snap["strategies"] if r["strategy_id"] == "smc_scalping")
    assert row["accepted"] == 1
    assert row["wins"] == 1
    assert row["losses"] == 1
    assert row["win_rate"] == 50.0
    assert row["avg_hold"] == 4.0
    assert row["max_drawdown"] >= 0


@pytest.mark.unit
def test_no_martingale_grid_on_default() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
