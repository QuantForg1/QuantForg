"""Unit tests — Institutional AI Scalping v5 quality upgrade."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    scalping_ite_config,
)
from app.domain.institutional_trading.ai_scalping.direction import (
    decide_scalping_direction,
)
from app.domain.institutional_trading.ai_scalping.multi_symbol import (
    rank_scalping_opportunities,
)
from app.domain.institutional_trading.ai_scalping.validation import (
    compare_backtest_vs_live,
)
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import TrendDirection


def _snap(
    *,
    macro: TrendDirection = TrendDirection.DOWN,
    primary: TrendDirection = TrendDirection.DOWN,
    alignment: int = 70,
) -> MagicMock:
    trend = MagicMock()
    trend.macro_bias = macro
    trend.primary = primary
    trend.alignment_score = alignment
    trend.why = "test"

    structure = MagicMock()
    structure.breaks_of_structure = []
    structure.changes_of_character = []
    structure.swings = []
    structure.last_swing_low = Decimal("1900")
    structure.last_swing_high = Decimal("1910")

    liq = MagicMock()
    liq.sweeps = [MagicMock(side="HIGH")]
    liq.pools = []

    quality = MagicMock()
    quality.total = 85
    quality.components = {"momentum": 75, "volume": 70, "liquidity": 70}

    session = MagicMock()
    session.session = MagicMock(value="london")
    session.allowed = True

    snap = MagicMock()
    snap.trend = trend
    snap.primary_structure = structure
    snap.liquidity = liq
    snap.order_blocks = MagicMock(order_blocks=[])
    snap.fair_value_gaps = MagicMock(active_gaps=[])
    snap.trade_quality = quality
    snap.session = session
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD"
    return snap


@pytest.mark.unit
def test_v5_mtf_and_risk_locked() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.version.startswith("ai-scalping-v5")
    assert cfg.direction_tf is Timeframe.H1
    assert cfg.structure_tf is Timeframe.M15
    assert cfg.entry_tf is Timeframe.M5
    assert cfg.execution_tf is Timeframe.M1
    assert cfg.risk_per_trade_pct <= Decimal("0.75")
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.never_prefer_buy_only is True
    assert cfg.typical_hold_max_minutes == 10
    ite = scalping_ite_config()
    assert ite.risk_per_trade_pct == cfg.risk_per_trade_pct


@pytest.mark.unit
def test_direction_balanced_sell_not_buy_default() -> None:
    snap = _snap(macro=TrendDirection.DOWN, primary=TrendDirection.DOWN)
    dec = decide_scalping_direction(snap)
    assert dec.direction is TradeDirection.SELL
    assert dec.sell_score > dec.buy_score

    snap2 = _snap(macro=TrendDirection.UP, primary=TrendDirection.UP)
    # Clear bearish liquidity sweep for BUY case
    snap2.liquidity.sweeps = [MagicMock(side="LOW")]
    dec2 = decide_scalping_direction(snap2)
    assert dec2.direction is TradeDirection.BUY


@pytest.mark.unit
def test_rank_best_opportunity_only() -> None:
    ranked = rank_scalping_opportunities(
        [
            {
                "symbol": "EURUSD",
                "reject": False,
                "direction": "BUY",
                "ai_confidence": 70,
                "expected_rr": 1.4,
                "trade_quality": 80,
            },
            {
                "symbol": "XAUUSD",
                "reject": False,
                "direction": "SELL",
                "ai_confidence": 90,
                "expected_rr": 1.8,
                "trade_quality": 88,
            },
            {
                "symbol": "GBPUSD",
                "reject": True,
                "direction": "BUY",
                "ai_confidence": 95,
            },
        ]
    )
    assert ranked["best"]["symbol"] == "XAUUSD"
    assert ranked["rejected_count"] == 1
    assert set(ranked["universe"]) == set(DEFAULT_SCALPING_UNIVERSE)


@pytest.mark.unit
def test_validation_requires_measurable_improvement() -> None:
    ok = compare_backtest_vs_live(
        backtest={
            "win_rate": 58,
            "profit_factor": 1.6,
            "drawdown": 4,
            "average_rr": 1.5,
        },
        live={
            "win_rate": 48,
            "profit_factor": 1.1,
            "drawdown": 8,
            "average_rr": 1.1,
        },
    )
    assert ok["recommend_deploy"] is True

    bad = compare_backtest_vs_live(
        backtest={"win_rate": 40, "profit_factor": 0.9, "drawdown": 12, "average_rr": 0.8},
        live={"win_rate": 50, "profit_factor": 1.2, "drawdown": 6, "average_rr": 1.2},
    )
    assert bad["recommend_deploy"] is False


@pytest.mark.unit
def test_dashboard_shape() -> None:
    from app.application.services.ai_scalping_dashboard import (
        build_ai_scalping_dashboard,
    )

    dash = build_ai_scalping_dashboard()
    assert dash["version"].startswith("ai-scalping-v5")
    assert dash["safeguards"]["allow_martingale"] is False
    assert "current_setup" in dash
    assert "diagnostics" in dash
