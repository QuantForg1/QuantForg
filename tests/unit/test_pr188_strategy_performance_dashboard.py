"""PR #188 — dashboard payload enrichment (observability only)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.institutional_trading.ai_scalping.strategies import (
    performance_monitor as perf,
    trade_outcome_store as outcomes,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_WHEN = datetime(2026, 11, 6, 12, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean() -> None:
    outcomes.reset_trade_outcome_store_for_tests()
    yield
    outcomes.reset_trade_outcome_store_for_tests()


def test_period_bucket_exposes_realized_vs_unrealized_and_sides() -> None:
    outcomes.record_trade_outcome(
        position_id=11,
        exit_deal_id=11,
        net_pnl=4.0,
        strategy_id="trend_continuation",
        side="BUY",
        closed_at=_WHEN,
        broker_login=12479147,
        costs_complete=True,
        commission=0.0,
        swap=0.0,
        attribution_confidence="bound_five_pack",
    )
    outcomes.record_trade_outcome(
        position_id=12,
        exit_deal_id=12,
        net_pnl=-2.0,
        strategy_id="smc_scalping",
        side="SELL",
        closed_at=_WHEN,
        broker_login=12479147,
        costs_complete=True,
        commission=0.0,
        swap=0.0,
        attribution_confidence="bound_five_pack",
    )
    rows = outcomes.list_trade_outcomes(broker_login=12479147, period="post_pr182")
    bucket = perf.build_period_bucket(rows, label="post_pr182", account=12479147)
    assert bucket["n"] == 2
    assert bucket["attribution_coverage_pct"] == 100.0
    assert bucket["realized_net_pnl"] == 2.0
    assert bucket["unrealized_pnl"] is None
    assert bucket["buy"]["n"] == 1
    assert bucket["sell"]["n"] == 1
    assert "win_rate" in bucket["buy"]
    assert "profit_factor" in bucket["sell"]
    assert bucket["side_comparison"]["buy"]["n"] == 1


def test_monitor_includes_protection_and_m1_without_mutating_flags() -> None:
    mon = perf.build_post182_performance_monitor(broker_login=12479147)
    assert mon["features"]["changes_trading_decisions"] is False
    assert mon["features"]["observability_only"] is True
    assert mon["features"]["m1_live_submit_unchanged"] is True
    assert mon["overview"]["label"] == "post_pr182"
    assert "capital_protection" in mon
    assert mon["capital_protection"]["buy_cascade"]["historical_block_count"] is None
    assert "m1" in mon
    assert "display_rule" in mon["m1"]
    assert mon["instrument"] == "XAUUSD"
    cards = mon["five_pack_scorecards_post_pr182"]
    assert any(c["strategy_id"] == "momentum_scalping" for c in cards)
    assert any(c["strategy_id"] is None for c in cards)


def test_account_isolation_in_monitor() -> None:
    outcomes.record_trade_outcome(
        position_id=21,
        exit_deal_id=21,
        net_pnl=1.0,
        strategy_id="breakout_scalping",
        side="BUY",
        closed_at=_WHEN,
        broker_login=12260878,
        costs_complete=True,
        commission=0.0,
        swap=0.0,
        attribution_confidence="bound_five_pack",
    )
    a = perf.build_post182_performance_monitor(broker_login=12479147)
    b = perf.build_post182_performance_monitor(broker_login=12260878)
    assert a["post_pr182"]["n"] == 0
    assert b["post_pr182"]["n"] == 1
    assert a["broker_login"] == 12479147
    assert b["broker_login"] == 12260878
