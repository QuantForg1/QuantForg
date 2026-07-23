"""Unit tests — Threshold Performance Analysis (offline research only)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.services.threshold_performance_analysis import (
    BASELINE_CONFLUENCE,
    BASELINE_QUALITY,
    _build_recommendation,
    compute_cell_metrics,
    matrix_to_csv,
    override_ite_config,
    simulate_trade_outcome,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.value_objects.identity import SymbolCode
from datetime import UTC, datetime, timedelta


def _bar(i: int, *, low: float, high: float, close: float) -> Candle:
    t0 = datetime(2026, 6, 1, tzinfo=UTC) + timedelta(minutes=15 * i)
    code = SymbolCode(value=GOLD_SYMBOL)
    return Candle.create(
        symbol_code=code,
        timeframe=Timeframe.M15,
        open_time=t0,
        close_time=t0 + timedelta(minutes=15),
        open=f"{close:.2f}",
        high=f"{high:.2f}",
        low=f"{low:.2f}",
        close=f"{close:.2f}",
        volume="1",
        tick_count=1,
    )


@pytest.mark.unit
class TestThresholdPerformanceAnalysis:
    def test_override_does_not_mutate_default(self) -> None:
        cfg = override_ite_config(quality_gate=70, confluence_gate=65)
        assert cfg.min_trade_quality_score == 70
        assert cfg.min_confluence_score == 65
        assert DEFAULT_ITE_CONFIG.min_trade_quality_score == 80
        assert DEFAULT_ITE_CONFIG.min_confluence_score == 80
        # replace identity
        assert cfg is not DEFAULT_ITE_CONFIG
        assert replace(DEFAULT_ITE_CONFIG).min_trade_quality_score == 80

    def test_simulate_tp_win(self) -> None:
        bars = [
            _bar(0, low=2399, high=2401, close=2400),
            _bar(1, low=2400, high=2412, close=2410),
        ]
        out = simulate_trade_outcome(
            direction="BUY",
            entry=2400,
            stop=2395,
            target=2410,
            bars_after=bars,
            spread=0.3,
            risk_amount=100,
        )
        assert out is not None
        assert out["result"] == "win"
        assert out["net_pnl"] is not None and out["net_pnl"] > 0

    def test_cell_metrics_and_recommendation_keep(self) -> None:
        metrics = compute_cell_metrics(
            total_signals=10,
            rejected=7,
            executed_trades=[
                {
                    "result": "win",
                    "net_pnl": 20,
                    "r_multiple": 2,
                    "hold_sec": 900,
                    "spread": 0.3,
                    "slippage": 0.15,
                },
                {
                    "result": "loss",
                    "net_pnl": -10,
                    "r_multiple": -1,
                    "hold_sec": 600,
                    "spread": 0.3,
                    "slippage": 0.15,
                },
            ],
        )
        assert metrics["executed_trades"] == 2
        assert metrics["win_rate"] == 0.5
        assert metrics["profit_factor"] == 2.0
        assert metrics["net_profit"] == 10.0

        matrix = [
            {
                "quality_gate": BASELINE_QUALITY,
                "confluence_gate": BASELINE_CONFLUENCE,
                "is_baseline": True,
                "net_profit": 50,
                "expectancy": 1.0,
                "maximum_drawdown_pct": 5.0,
                "sharpe_ratio": 1.0,
                "profit_factor": 1.5,
            },
            {
                "quality_gate": 70,
                "confluence_gate": 70,
                "is_baseline": False,
                "net_profit": 40,  # worse profit
                "expectancy": 0.5,
                "maximum_drawdown_pct": 4.0,
                "sharpe_ratio": 0.8,
                "profit_factor": 1.2,
            },
        ]
        rec = _build_recommendation(matrix)
        assert rec["action"] == "keep_production_thresholds_unchanged"
        assert rec["never_auto_lowers_thresholds"] is True
        csv = matrix_to_csv({"matrix": [{**matrix[0], **metrics}]})
        assert "quality_gate" in csv
