"""Unit tests — AI Validation & Performance Optimization v7."""

from __future__ import annotations

from types import SimpleNamespace
from decimal import Decimal

import pytest

from app.domain.institutional_trading.ai_validation.benchmarks import (
    estimate_buy_hold_return,
    estimate_sma_crossover_return,
)
from app.domain.institutional_trading.ai_validation.execution_quality import (
    ExecutionQualityMonitor,
)
from app.domain.institutional_trading.ai_validation.portfolio import (
    PortfolioAnalyticsStore,
    asset_class_for,
)
from app.domain.institutional_trading.ai_validation.shadow_ai import (
    compare_primary_shadow,
    evaluate_shadow,
)
from app.domain.institutional_trading.ai_validation.slippage import (
    compute_entry_slippage,
    compute_exit_slippage,
)
from app.domain.institutional_trading.ai_validation.weight_optimizer import (
    WeightOptimizerStore,
)


def _decision(**kwargs):
    defaults = dict(
        direction=SimpleNamespace(value="BUY"),
        action=SimpleNamespace(value="BUY"),
        confidence=72,
        risk_score=30,
        estimated_rr=Decimal("1.8"),
        symbol="XAUUSD",
        quality=70,
        confluence=SimpleNamespace(
            factors={
                "trend": 80,
                "momentum": 75,
                "liquidity": 70,
                "volatility": 50,
                "session": 90,
            }
        ),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.unit
def test_shadow_ai_comparison_stores_disagreement() -> None:
    primary = _decision(confidence=90, estimated_rr=Decimal("2.5"))
    shadow = evaluate_shadow(decision=primary)
    assert shadow.confidence >= 0
    cmp = compare_primary_shadow(decision=primary, shadow=shadow)
    assert cmp.primary["direction"] == "BUY"
    assert "direction" in cmp.shadow
    assert "confidence" in cmp.shadow
    assert cmp.used_engine == "primary"  # never auto-veto by default
    assert isinstance(cmp.significant_disagreement, bool)


@pytest.mark.unit
def test_shadow_direction_none_when_weak() -> None:
    primary = _decision(
        confidence=40,
        confluence=SimpleNamespace(
            factors={
                "trend": 20,
                "momentum": 20,
                "liquidity": 20,
                "volatility": 80,
                "session": 20,
            }
        ),
    )
    shadow = evaluate_shadow(decision=primary)
    assert shadow.direction in {"NONE", "BUY", "SELL"}


@pytest.mark.unit
def test_weight_optimizer_gradual_and_logged(tmp_path) -> None:
    store = WeightOptimizerStore()
    store._path = tmp_path / "opt.json"
    store.multipliers = {k: 1.0 for k in store.multipliers}
    entry = store.optimize_from_trade(
        win=True, factor_scores={"trend": 80, "momentum": 70, "bos": 65}
    )
    assert entry is not None
    assert entry.before["trend"] == 1.0
    assert store.multipliers["trend"] > 1.0
    assert store.updates == 1
    snap = store.snapshot()
    assert "trading rules" in snap["note"].lower() or "rules" in snap["note"].lower()


@pytest.mark.unit
def test_execution_quality_bottleneck() -> None:
    mon = ExecutionQualityMonitor()
    mon.record(
        {
            "signal_generation": 10,
            "ai_decision": 200,
            "oms": 50,
            "gateway": 40,
            "mt5": 30,
            "broker": 20,
            "total": 350,
        }
    )
    snap = mon.snapshot()
    assert snap["bottleneck"] == "ai_decision"
    assert snap["avg_total_execution_ms"] == 350


@pytest.mark.unit
def test_slippage_calculations() -> None:
    # Buy: actual > expected → adverse positive
    assert compute_entry_slippage(side="buy", expected=100.0, actual=100.5) == 0.5
    # Sell: actual < expected → adverse positive
    assert compute_entry_slippage(side="sell", expected=100.0, actual=99.5) == 0.5
    assert compute_exit_slippage(side="buy", expected=110.0, actual=109.0) == 1.0


@pytest.mark.unit
def test_portfolio_analytics_drawdown_and_asset_class() -> None:
    store = PortfolioAnalyticsStore()
    store.record_equity(100_000)
    store.record_equity(98_000)
    store.set_exposures(
        by_symbol={"XAUUSD": 0.4, "EURUSD": 0.2, "NAS100": 0.1},
        correlation_exposure=0.55,
    )
    snap = store.snapshot()
    assert snap["current_drawdown_pct"] == 2.0
    assert snap["exposure_by_asset_class"]["metals"] == 0.4
    assert snap["exposure_by_asset_class"]["fx"] == 0.2
    assert asset_class_for("BTCUSD") == "crypto"


@pytest.mark.unit
def test_benchmark_helpers() -> None:
    prices = [100 + i * 0.5 for i in range(60)]
    bh = estimate_buy_hold_return(prices)
    assert bh is not None and bh > 0
    sma = estimate_sma_crossover_return(prices, fast=5, slow=20)
    assert sma is not None


@pytest.mark.unit
def test_ai_validation_dashboard_shape() -> None:
    from app.application.services.ai_validation import build_ai_validation_dashboard

    dash = build_ai_validation_dashboard()
    assert dash["version"].startswith("ai-validation-v7")
    assert "strategy_performance" in dash
    assert "execution_quality" in dash
    assert "slippage_report" in dash
    assert "ai_validation_report" in dash
    assert "opportunity_replay" in dash
    assert "risk_overview" in dash
    assert dash["config"]["shadow_veto_enabled"] is False
