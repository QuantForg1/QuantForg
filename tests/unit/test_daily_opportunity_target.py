"""Tests for daily opportunity target — never forces trades."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.daily_opportunity_target import (
    ClosedTradeRecord,
    DailyOpportunityTargetTracker,
    compute_performance_metrics,
    reset_daily_opportunity_tracker,
)


def test_target_never_forces_trade() -> None:
    assert (
        DailyOpportunityTargetTracker.should_force_trade_for_target(
            trades_today=0, target=3, valid_setups=0
        )
        is False
    )
    assert (
        DailyOpportunityTargetTracker.should_force_trade_for_target(
            trades_today=0, target=3, valid_setups=5
        )
        is False
    )
    assert (
        DailyOpportunityTargetTracker.should_force_trade_for_target(
            trades_today=2, target=3, valid_setups=1
        )
        is False
    )


def test_zero_valid_setups_keeps_seeking_without_execution() -> None:
    reset_daily_opportunity_tracker()
    t = DailyOpportunityTargetTracker(target_trades_per_day=3)
    t.note_analysis(decision="NO_TRADE")
    assert t.trades_today == 0
    assert t.seeking_mode() == "seeking_quality_opportunities"
    assert t.snapshot()["force_trade_for_target"] is False


def test_one_and_two_executions_remain_below_target() -> None:
    t = DailyOpportunityTargetTracker(target_trades_per_day=3)
    t.note_quality_setup_seen()
    t.note_trade_executed(symbol="EURUSD")
    assert t.trades_today == 1
    assert t.remaining_trade_opportunities() == 2
    t.note_trade_executed(symbol="GBPUSD")
    assert t.trades_today == 2
    assert t.remaining_trade_opportunities() == 1
    assert t.seeking_mode() == "seeking_quality_opportunities"


def test_three_executions_switch_to_exceptional_only_mode() -> None:
    t = DailyOpportunityTargetTracker(target_trades_per_day=3)
    for i in range(3):
        t.note_trade_executed(symbol=f"SYM{i}")
    assert t.trades_today == 3
    assert t.remaining_trade_opportunities() == 0
    assert t.seeking_mode() == "target_reached_exceptional_only"
    # Still never forces
    assert t.snapshot()["forced"] is False


def test_above_target_still_requires_gates() -> None:
    t = DailyOpportunityTargetTracker(target_trades_per_day=3)
    for i in range(4):
        t.note_trade_executed(symbol=f"SYM{i}")
    assert t.seeking_mode() == "above_target_gates_unchanged"
    assert (
        DailyOpportunityTargetTracker.should_force_trade_for_target(
            trades_today=4, target=3, valid_setups=10
        )
        is False
    )


def test_reject_records_first_gate() -> None:
    t = DailyOpportunityTargetTracker()
    t.note_quality_setup_seen()
    t.note_quality_setup_rejected(gate="spread_too_wide")
    snap = t.snapshot()
    assert snap["quality_setups_rejected"] == 1
    assert snap["last_reject_gate"] == "spread_too_wide"
    assert snap["trades_today"] == 0


def test_expectancy_calculation() -> None:
    trades = [
        ClosedTradeRecord(
            symbol="A",
            strategy="s",
            session="",
            market_regime="",
            realized_pnl=20.0,
            risk_pct_at_entry=0.5,
            equity_at_exit=100.0,
            realized_r=2.0,
            expected_r=1.5,
            holding_seconds=60,
            exit_reason="tp",
            won=True,
            closed_at="2026-01-01T00:00:00Z",
        ),
        ClosedTradeRecord(
            symbol="B",
            strategy="s",
            session="",
            market_regime="",
            realized_pnl=-10.0,
            risk_pct_at_entry=0.5,
            equity_at_exit=90.0,
            realized_r=-1.0,
            expected_r=1.5,
            holding_seconds=60,
            exit_reason="sl",
            won=False,
            closed_at="2026-01-01T01:00:00Z",
        ),
    ]
    m = compute_performance_metrics(trades)
    assert m.win_rate == 0.5
    assert m.average_win == 20.0
    assert m.average_loss == 10.0
    # (0.5*20) - (0.5*10) = 5
    assert m.expectancy_per_trade == 5.0
    assert m.profit_factor == 2.0
    assert m.sample_size == 2


def test_loss_updates_stats_without_revenge_flag() -> None:
    t = DailyOpportunityTargetTracker()
    t.note_trade_closed(
        ClosedTradeRecord(
            symbol="XAUUSD_i",
            strategy="scalping",
            session="london",
            market_regime="trend",
            realized_pnl=-5.0,
            risk_pct_at_entry=1.0,
            equity_at_exit=95.0,
            realized_r=-1.0,
            expected_r=1.2,
            holding_seconds=120,
            exit_reason="sl",
            won=False,
            closed_at="2026-01-01T00:00:00Z",
        )
    )
    perf = t.performance()
    assert perf.win_rate == 0.0
    assert perf.max_consecutive_losses == 1
    assert t.snapshot()["force_trade_for_target"] is False


def test_config_exposes_target_trades_per_day() -> None:
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    assert DEFAULT_AI_SCALPING_CONFIG.target_trades_per_day == 3
    d = DEFAULT_AI_SCALPING_CONFIG.to_dict()
    assert d["target_trades_per_day"] == 3
    assert d["post_event_rescan_enabled"] is True
