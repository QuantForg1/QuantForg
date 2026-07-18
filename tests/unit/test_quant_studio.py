"""Unit tests for Quant Studio domain — no invented market data."""

from __future__ import annotations

from uuid import uuid4

from app.domain.quant_studio.analytics import build_professional_analytics
from app.domain.quant_studio.marketplace import StrategyMarketplaceStore
from app.domain.quant_studio.monte_carlo import run_monte_carlo
from app.domain.quant_studio.optimizer import suggest_optimizations
from app.domain.quant_studio.strategy_review import review_strategy
from app.domain.quant_studio.visual_builder import BLOCK_CATALOG, compile_strategy_graph
from app.domain.quant_studio.walkforward import summarize_walkforward_stability


def test_block_catalog_covers_modules() -> None:
    cats = {b["category"] for b in BLOCK_CATALOG}
    assert "Indicators" in cats
    assert "Exit" in cats
    assert "AI" in cats


def test_compile_empty_graph() -> None:
    result = compile_strategy_graph({"nodes": [], "edges": []})
    assert result["status"] == "unavailable"
    assert result["autonomous_trading"] is False


def test_compile_graph_with_exit() -> None:
    result = compile_strategy_graph(
        {
            "nodes": [
                {"type": "indicator", "params": {"name": "ema", "period": 20}},
                {
                    "type": "exit",
                    "params": {"sl_distance": "0.0015", "tp_distance": "0.003"},
                },
                {"type": "execution", "params": {"side": "buy"}},
            ],
            "edges": [{"from": 0, "to": 2}],
        }
    )
    assert result["status"] == "available"
    assert result["assumptions"]["stop_loss_distance"] == "0.0015"
    assert result["never_submits_orders"] is True


def test_monte_carlo_empty() -> None:
    assert run_monte_carlo([])["status"] == "unavailable"


def test_monte_carlo_bootstrap() -> None:
    pnls = [10.0, -5.0, 8.0, -3.0, 12.0, -4.0] * 5
    result = run_monte_carlo(pnls, simulations=200, initial_equity=10_000, seed=1)
    assert result["status"] == "available"
    assert result["simulations"] == 200
    assert "confidence" in result
    assert result["worst_case"] <= result["best_case"]
    assert result["autonomous_trading"] is False


def test_strategy_review() -> None:
    result = review_strategy(
        metrics={
            "win_rate": 58,
            "profit_factor": 1.8,
            "sharpe_ratio": 1.2,
            "max_drawdown_pct": 6,
            "expectancy": 12,
            "trade_count": 120,
        },
        assumptions={"stop_loss_distance": "0.002", "take_profit_distance": "0.004"},
    )
    assert result["status"] == "available"
    assert result["strengths"]
    assert result["never_modifies_user_settings"] is True


def test_optimizer_advisory_only() -> None:
    result = suggest_optimizations(
        metrics={
            "average_r": 0.6,
            "win_rate": 40,
            "max_drawdown_pct": 18,
            "profit_factor": 1.0,
        },
        assumptions={
            "stop_loss_distance": "0.002",
            "take_profit_distance": "0.003",
            "lot_size": "0.2",
        },
        symbol="EURUSD",
        timeframe="H1",
    )
    assert result["status"] == "available"
    assert result["applied"] is False
    assert result["never_modifies_user_settings"] is True
    assert any(
        s["field"] in {"tp_distance", "rr", "risk", "sl_distance"}
        for s in result["suggestions"]
    )


def test_analytics_from_equity_trades() -> None:
    equity = [
        {"timestamp": "2024-01-01T00:00:00+00:00", "equity": 10000, "drawdown_pct": 0},
        {"timestamp": "2024-01-15T00:00:00+00:00", "equity": 10100, "drawdown_pct": 1},
        {
            "timestamp": "2024-02-01T00:00:00+00:00",
            "equity": 10200,
            "drawdown_pct": 0.5,
        },
    ]
    trades = [
        {"pnl": 50, "closed_at": "2024-01-02T10:00:00+00:00"},
        {"pnl": -20, "closed_at": "2024-01-03T11:00:00+00:00"},
    ]
    result = build_professional_analytics(equity_curve=equity, trades=trades)
    assert result["status"] == "available"
    assert result["trade_distribution"]["win"] == 1
    assert result["monthly_returns"]


def test_walkforward_stability() -> None:
    folds = [
        {"is_profit_factor": 1.5, "oos_profit_factor": 1.3},
        {"is_profit_factor": 1.4, "oos_profit_factor": 1.2},
        {"is_profit_factor": 1.6, "oos_profit_factor": 1.1},
    ]
    result = summarize_walkforward_stability(folds)
    assert result["status"] == "available"
    assert result["stability_score"] is not None


def test_marketplace_save_clone_publish_favorite() -> None:
    store = StrategyMarketplaceStore()
    uid = uuid4()
    other = uuid4()
    saved = store.save(
        user_id=uid,
        name="Alpha",
        graph={"nodes": [{"type": "price"}], "edges": []},
        assumptions={"lot_size": "0.1"},
    )
    assert saved["status"] == "available"
    sid = saved["strategy"]["id"]

    # version bump
    v2 = store.save(
        user_id=uid,
        name="Alpha",
        graph={"nodes": [{"type": "exit"}], "edges": []},
        assumptions={"lot_size": "0.2"},
        strategy_id=sid,
    )
    assert v2["strategy"]["latest_version"] == 2

    pub = store.publish(user_id=uid, strategy_id=sid, published=True)
    assert pub["strategy"]["published"] is True

    cloned = store.clone(user_id=other, strategy_id=sid)
    assert cloned["status"] == "available"
    assert cloned["strategy"]["clone_of"] == sid

    fav = store.favorite(user_id=other, strategy_id=sid, favorited=True)
    assert fav["favorite"] is True

    items = store.list_for_user(other)
    assert any(i["id"] == sid for i in items)
