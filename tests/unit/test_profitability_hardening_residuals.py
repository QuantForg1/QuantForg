"""Regression: no fantasy RR; symbol-class contract size; close telemetry."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.strategy_performance_telemetry import (
    StrategyPerformanceTelemetry,
)
from app.domain.entities.risk_engine import contract_size_for_symbol
from app.domain.institutional_trading.ai_scalping.daily_opportunity_target import (
    ClosedTradeRecord,
    compute_performance_metrics,
)


@pytest.mark.unit
@pytest.mark.trading_core
def test_contract_size_never_inherits_gold_into_fx() -> None:
    assert contract_size_for_symbol("EURUSD", default=Decimal("0")) == Decimal(
        "100000"
    )
    assert contract_size_for_symbol("XAUUSD", default=Decimal("0")) == Decimal("100")
    assert contract_size_for_symbol("BTCUSD", default=Decimal("0")) == Decimal("1")
    # Unknown index: do not invent gold
    assert contract_size_for_symbol("US500", default=Decimal("0")) == Decimal("0")


@pytest.mark.unit
@pytest.mark.trading_core
def test_closed_trade_record_optional_telemetry_defaults() -> None:
    row = ClosedTradeRecord(
        symbol="EURUSD",
        strategy="scalp",
        session="london",
        market_regime="strong_trend",
        realized_pnl=12.5,
        risk_pct_at_entry=0.0,
        equity_at_exit=0.0,
        realized_r=1.2,
        expected_r=1.5,
        holding_seconds=120.0,
        exit_reason="tp",
        won=True,
        closed_at=datetime.now(UTC).isoformat(),
    )
    assert row.planned_risk_usd is None
    assert row.be_reached is None
    metrics = compute_performance_metrics([row])
    assert metrics.sample_size == 1
    assert metrics.win_rate == 1.0


@pytest.mark.unit
@pytest.mark.trading_core
def test_observe_close_records_asymmetry_fields() -> None:
    tel = StrategyPerformanceTelemetry()
    tel.observe_fill(ticket=42, direction="buy", entry="1.1000")
    trace = tel.observe_close(
        ticket=42,
        exit_price="1.1015",
        realized_pnl=15.0,
        realized_r=1.5,
        exit_reason="take_profit",
        hold_seconds=90,
        planned_risk_usd=10.0,
        planned_reward_usd=15.0,
        be_reached=True,
        trailing_activated=False,
        intelligence_alignment="ALIGNED",
        opportunity_score=81,
        setup_family="fvg_retest",
        max_favorable_r=1.6,
        consecutive_losses_at_close=0,
    )
    assert trace is not None
    assert trace["planned_risk_usd"] == 10.0
    assert trace["planned_reward_usd"] == 15.0
    assert trace["be_reached"] is True
    assert trace["intelligence_alignment"] == "ALIGNED"
    assert trace["opportunity_score"] == 81


@pytest.mark.unit
@pytest.mark.trading_core
def test_no_fantasy_rr_when_structure_targets_lack_tp() -> None:
    from unittest.mock import MagicMock

    from app.domain.institutional_trading.ai_scalping import scoring as scoring_mod
    from app.domain.institutional_trading.ai_scalping.config import (
        AiScalpingConfig,
    )
    from app.domain.institutional_trading.ai_scalping.structure_targets import (
        StructureTargets,
    )
    from app.domain.market_structure.enums import TrendDirection

    snap = MagicMock()
    trend = MagicMock()
    trend.macro_bias = TrendDirection.DOWN
    trend.primary = TrendDirection.DOWN
    trend.alignment_score = 80
    trend.why = "test"
    snap.trend = trend
    structure = MagicMock()
    structure.breaks_of_structure = [MagicMock()]
    structure.changes_of_character = [MagicMock()]
    structure.swings = []
    structure.last_swing_low = Decimal("1900")
    structure.last_swing_high = Decimal("1910")
    snap.primary_structure = structure
    snap.liquidity = MagicMock(sweeps=[MagicMock(side="HIGH")], pools=[])
    snap.order_blocks = MagicMock(order_blocks=[])
    snap.fair_value_gaps = MagicMock(active_gaps=[MagicMock()])
    quality = MagicMock()
    quality.total = 85
    quality.components = {"momentum": 75, "volume": 70, "liquidity": 70}
    snap.trade_quality = quality
    session = MagicMock()
    session.session = MagicMock(value="london")
    session.allowed = True
    snap.session = session
    snap.spread = Decimal("0.20")
    snap.symbol = "XAUUSD"
    snap.news = SimpleNamespace(blocked=False, reason="")

    cfg = AiScalpingConfig(fixed_tp_r=Decimal("1.5"), min_expected_rr=Decimal("1.20"))

    original = scoring_mod.compute_structure_targets

    def _no_tp(*_a, **_k):
        return StructureTargets(
            entry=Decimal("1910"),
            stop_loss=Decimal("1908"),
            take_profit=None,
            stop_distance=Decimal("2"),
            expected_rr=None,
            reason="Cannot place TP",
        )

    scoring_mod.compute_structure_targets = _no_tp  # type: ignore[assignment]
    try:
        score = scoring_mod.score_scalping_setup(
            snap,
            atr=Decimal("5"),
            mid=Decimal("1910"),
            config=cfg,
            symbol="XAUUSD",
        )
    finally:
        scoring_mod.compute_structure_targets = original  # type: ignore[assignment]

    assert score.expected_rr is None
    assert score.reject is True
    assert "WAIT_NO_VALID_TP_ROOM" in (score.reject_reason or "")
