"""Unit tests for Quant Research Lab domain — no invented market data."""

from __future__ import annotations

from uuid import uuid4

from app.domain.research_lab.comparison import (
    compare_strategies,
    pick_dashboard_leaders,
)
from app.domain.research_lab.library import get_strategy, list_strategy_library
from app.domain.research_lab.parameter_lab import sandbox_parameters
from app.domain.research_lab.regime import classify_regime, strategy_regime_fit
from app.domain.research_lab.reports import build_research_report
from app.domain.research_lab.store import ResearchLabStore, get_research_store


def test_library_covers_required_modules() -> None:
    keys = {s["key"] for s in list_strategy_library()}
    for required in (
        "trend_following",
        "liquidity_sweep",
        "breakout",
        "mean_reversion",
        "momentum",
        "session_breakout",
        "order_block",
        "fvg",
        "custom_rules",
    ):
        assert required in keys
    assert get_strategy("fvg") is not None


def test_compare_never_invents_metrics() -> None:
    result = compare_strategies([])
    assert result["status"] == "unavailable"

    result = compare_strategies(
        [
            {
                "strategy_key": "a",
                "name": "A",
                "metrics": {
                    "sharpe_ratio": 1.2,
                    "profit_factor": 1.5,
                    "trade_count": 40,
                },
            },
            {
                "strategy_key": "b",
                "name": "B",
                "metrics": {"sharpe_ratio": 0.3, "max_drawdown_pct": 25},
            },
        ]
    )
    assert result["status"] == "available"
    assert result["items"][1]["win_rate"] is None
    leaders = pick_dashboard_leaders(result)
    assert leaders["best"]["strategy_key"] == "a"


def test_sandbox_never_mutates_production_defaults() -> None:
    from app.domain.research_lab.parameter_lab import PRODUCTION_DEFAULTS

    before = dict(PRODUCTION_DEFAULTS)
    sandbox = sandbox_parameters({"ema_fast": 9, "unknown_param": 1})
    assert sandbox["parameters"]["ema_fast"] == 9
    assert before == PRODUCTION_DEFAULTS
    assert sandbox["production_defaults_unchanged"] is True
    assert sandbox["rejected"]


def test_regime_classification() -> None:
    regime = classify_regime(
        structure={
            "status": "available",
            "market_regime": "Trending up",
            "trend": "Bullish",
            "volatility": "High",
            "momentum": "Strong up",
        },
        market_context={"session": "London"},
        news_risk="high",
    )
    assert regime["status"] == "available"
    assert "Trending" in regime["regimes"]
    assert "High Volatility" in regime["regimes"]
    assert "News Driven" in regime["regimes"]

    strategy = get_strategy("trend_following")
    assert strategy is not None
    fit = strategy_regime_fit(strategy, regime)
    assert fit["suitable"] is True


def test_promotion_eligibility_store() -> None:
    store = ResearchLabStore()
    uid = uuid4()
    evaluation = store.evaluate_promotion(
        {
            "metrics": {
                "profit_factor": 1.5,
                "sharpe_ratio": 1.0,
                "max_drawdown_pct": 8,
                "trade_count": 50,
            },
            "stability": {"stability_score": 0.8},
        }
    )
    assert evaluation["eligible_for_decision_engine"] is True
    assert evaluation["never_auto_forwards"] is True
    row = store.set_eligibility(
        user_id=uid,
        strategy_key="trend_following",
        eligible=True,
        evidence={"evaluation": evaluation},
    )
    assert row["decision_engine_untouched"] is True
    assert store.list_eligibility(uid)


def test_research_report_advisory() -> None:
    report = build_research_report(
        strategy={"key": "momentum", "name": "Momentum"},
        metrics={"sharpe_ratio": 1.1},
        regime={"primary": "Trending"},
        review={"status": "available"},
        validation={"backtest_status": "available"},
        promotion={"eligible_for_decision_engine": False},
    )
    assert report["format"] == "pdf_ready_json"
    assert report["advisory_only"] is True
    assert report["autonomous_trading"] is False


def test_global_store_singleton() -> None:
    a = get_research_store()
    b = get_research_store()
    assert a is b
