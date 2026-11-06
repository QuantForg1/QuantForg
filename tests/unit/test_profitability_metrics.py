"""Deterministic profitability scorecards — no broker orders."""

from __future__ import annotations

import pytest

from app.domain.institutional_trading.ai_scalping.strategies import (
    profitability_metrics as pm,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_breakeven_win_rate_and_expectancy() -> None:
    rows = [
        {"net_pnl": 2.0},
        {"net_pnl": 2.0},
        {"net_pnl": -3.0},
        {"net_pnl": -3.0},
    ]
    card = pm.build_performance_scorecard(rows, label="toy")
    assert card.n == 4
    assert card.wins == 2
    assert card.losses == 2
    assert card.avg_win == 2.0
    assert card.avg_loss == -3.0
    assert card.expectancy == -0.5
    # BE = 3 / (2+3) = 0.6
    assert card.breakeven_win_rate == pytest.approx(0.6)
    assert card.max_consecutive_losses == 2
    assert card.classification == "Negative expectancy (small sample — provisional)"


def test_positive_sample_stays_provisional_under_20() -> None:
    rows = [{"net_pnl": 1.0}] * 10 + [{"net_pnl": -0.5}] * 5
    card = pm.build_performance_scorecard(rows, label="small_pos")
    assert card.expectancy > 0
    assert card.classification == "Promising but insufficient sample"


def test_demonstrated_positive_requires_sufficient_n() -> None:
    rows = [{"net_pnl": 1.0}] * 15 + [{"net_pnl": -0.5}] * 10
    card = pm.build_performance_scorecard(rows, label="ok")
    assert card.n == 25
    assert card.expectancy > 0
    assert card.classification == "Demonstrated positive expectancy"


def test_empty_is_insufficient() -> None:
    card = pm.build_performance_scorecard([], label="empty")
    assert card.n == 0
    assert card.classification == "Insufficient data"
    assert pm.classify_expectancy(n=0, expectancy=0.0, profit_factor=None) == (
        "Insufficient data"
    )


def test_all_wins_profit_factor_none_means_infinite() -> None:
    card = pm.build_performance_scorecard(
        [{"net_pnl": 1.0}, {"net_pnl": 2.0}], label="wins"
    )
    assert card.profit_factor is None
    assert card.gross_loss == 0.0
