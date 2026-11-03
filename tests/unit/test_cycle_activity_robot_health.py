"""Phase-3 cycle activity + robot health monitor."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.strategies.cycle_activity import (
    record_blocked_by_risk,
    record_cycle_start,
    record_soe_verdict,
    record_strategy_evaluation,
    reset_cycle_activity,
    snapshot_cycle_activity,
)
from app.domain.institutional_trading.ai_scalping.strategies.monitoring import (
    build_robot_health_monitor,
)
from app.domain.institutional_trading.ai_scalping.strategies.orchestrator import (
    ORCHESTRATION_VERSION,
)
from app.domain.institutional_trading.ai_scalping.strategies.stats import (
    StrategyStatsBook,
)


@pytest.fixture(autouse=True)
def _clear_activity() -> None:
    reset_cycle_activity()
    yield
    reset_cycle_activity()


@pytest.mark.unit
def test_cycle_activity_records_evaluations_and_signal() -> None:
    record_cycle_start(symbol="XAUUSD", quote_age_seconds=1.2, regime="strong_trend")
    record_strategy_evaluation(
        strategy_id="smc_scalping",
        name="SMC Scalping",
        passed=True,
        direction="BUY",
        quality=88,
        confidence=84,
    )
    record_strategy_evaluation(
        strategy_id="range_mean_reversion",
        name="Range Mean-Reversion Scalping",
        passed=False,
        direction="NONE",
        quality=40,
        confidence=30,
        reject_reason="Regime strong_trend not in ('range', 'compression')",
    )
    record_soe_verdict(
        decision="BUY",
        reasons=("SOE selected smc_scalping",),
        selected_strategy_id="smc_scalping",
    )
    snap = snapshot_cycle_activity()
    assert snap["cycles_observed"] == 1
    assert snap["last_symbol"] == "XAUUSD"
    assert snap["last_soe_decision"] == "BUY"
    assert snap["strategies"]["smc_scalping"]["status"] == "SIGNAL_GENERATED"
    assert (
        snap["strategies"]["range_mean_reversion"]["status"] == "ACTIVE_NO_VALID_SETUP"
    )


@pytest.mark.unit
def test_stale_data_marks_strategies_unavailable() -> None:
    record_strategy_evaluation(
        strategy_id="trend_continuation",
        name="Trend Continuation Scalping",
        passed=True,
        direction="SELL",
        quality=90,
        confidence=88,
    )
    record_soe_verdict(
        decision="NO_TRADE",
        reasons=("Stale market data",),
        stale_data=True,
    )
    snap = snapshot_cycle_activity()
    assert snap["strategies"]["trend_continuation"]["status"] == "DATA_UNAVAILABLE"


@pytest.mark.unit
def test_blocked_by_risk_updates_selected() -> None:
    record_strategy_evaluation(
        strategy_id="momentum_scalping",
        name="Momentum Scalping",
        passed=True,
        direction="BUY",
        quality=86,
        confidence=82,
    )
    record_soe_verdict(
        decision="BUY",
        selected_strategy_id="momentum_scalping",
    )
    record_blocked_by_risk(
        strategy_id="momentum_scalping",
        reason="OWNER_MIN_REWARD_RISK",
    )
    snap = snapshot_cycle_activity()
    assert snap["strategies"]["momentum_scalping"]["status"] == "BLOCKED_BY_RISK"


@pytest.mark.unit
def test_robot_health_monitor_evidence_statuses(tmp_path: Path) -> None:
    record_cycle_start(symbol="XAUUSD", quote_age_seconds=0.5, regime="strong_trend")
    for sid, name, passed in (
        ("smc_scalping", "SMC Scalping", True),
        ("trend_continuation", "Trend Continuation Scalping", False),
        ("breakout_scalping", "Breakout Scalping", False),
        ("range_mean_reversion", "Range Mean-Reversion Scalping", False),
        ("momentum_scalping", "Momentum Scalping", False),
    ):
        record_strategy_evaluation(
            strategy_id=sid,
            name=name,
            passed=passed,
            direction="BUY" if passed else "NONE",
            quality=88 if passed else 50,
            confidence=84 if passed else 40,
            reject_reason=None if passed else "filters",
        )
    record_soe_verdict(
        decision="BUY",
        reasons=("selected",),
        selected_strategy_id="smc_scalping",
    )
    mon = build_robot_health_monitor(
        book=StrategyStatsBook(_path=tmp_path / "stats.json")
    )
    assert mon["orchestration_version"] == ORCHESTRATION_VERSION
    assert mon["auto_authorize_live"] is False
    assert mon["mutates_engines"] is False
    assert mon["robot"]["market_data_fresh"] is True
    by_id = {s["strategy_id"]: s for s in mon["strategies"]}
    assert by_id["smc_scalping"]["operational_status"] == "SIGNAL_GENERATED"
    assert by_id["trend_continuation"]["operational_status"] == "ACTIVE_NO_VALID_SETUP"
    assert mon["m1"]["owner_controlled"] is True
    assert mon["m1"]["auto_changed"] is False
    assert mon["risk_policy_defaults"]["minimum_net_reward_risk"] == "1.50"
    assert mon["risk_policy_defaults"]["max_concurrent_positions"] == 1
