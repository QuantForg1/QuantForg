"""PR #186 — durable attribution + post-#182 monitoring. No broker orders."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.application.services.close_attribution import (
    BrokerExitEvidence,
    record_broker_confirmed_close,
    reset_close_attribution_ledger_for_tests,
)
from app.domain.institutional_trading.ai_scalping.strategies import (
    attribution_store as attr,
    performance_monitor as perf,
    trade_outcome_store as outcomes,
)
from app.domain.institutional_trading.ai_scalping.strategies.registry import (
    list_strategy_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_WHEN = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean(tmp_path: Path) -> None:
    outcomes.reset_trade_outcome_store_for_tests()
    attr.reset_strategy_attribution_store_for_tests(tmp_path / "attr.json")
    reset_close_attribution_ledger_for_tests(tmp_path / "ledger.json")
    yield
    outcomes.reset_trade_outcome_store_for_tests()
    attr.reset_strategy_attribution_store_for_tests(tmp_path / "attr2.json")


def test_five_pack_registry_ids_are_stable() -> None:
    ids = set(list_strategy_ids())
    assert ids == set(attr.FIVE_PACK_STRATEGY_IDS)
    assert len(ids) == 5


def test_trade_outcome_idempotent_and_unknown_stays_unknown() -> None:
    assert (
        outcomes.record_trade_outcome(
            position_id=9001,
            exit_deal_id=1,
            net_pnl=-2.5,
            strategy_id=None,
            commission=0.0,
            swap=0.0,
            costs_complete=True,
            closed_at=_WHEN,
            broker_login=12479147,
            side="SELL",
        )
        == "created"
    )
    assert (
        outcomes.record_trade_outcome(
            position_id=9001,
            exit_deal_id=1,
            net_pnl=-2.5,
            closed_at=_WHEN,
        )
        == "duplicate"
    )
    rows = outcomes.list_trade_outcomes(broker_login=12479147)
    assert len(rows) == 1
    assert rows[0].strategy_id is None
    assert rows[0].attribution_confidence == "unknown"


def test_fabricated_ite_primary_stripped_from_outcome() -> None:
    assert (
        outcomes.record_trade_outcome(
            position_id=9002,
            exit_deal_id=2,
            net_pnl=1.0,
            strategy_id="ite_primary",
            costs_complete=False,
            closed_at=_WHEN,
            broker_login=12479147,
        )
        == "created"
    )
    row = outcomes.list_trade_outcomes(broker_login=12479147)[0]
    assert row.strategy_id is None
    assert row.costs_complete is False


def test_account_isolation_for_outcomes() -> None:
    outcomes.record_trade_outcome(
        position_id=1,
        exit_deal_id=10,
        net_pnl=-1,
        broker_login=12479147,
        closed_at=_WHEN,
        costs_complete=True,
        commission=0.0,
        swap=0.0,
    )
    outcomes.record_trade_outcome(
        position_id=2,
        exit_deal_id=20,
        net_pnl=2,
        broker_login=12260878,
        closed_at=_WHEN,
        costs_complete=True,
        commission=0.0,
        swap=0.0,
    )
    assert len(outcomes.list_trade_outcomes(broker_login=12479147)) == 1
    assert len(outcomes.list_trade_outcomes(broker_login=12260878)) == 1


def test_broker_confirmed_close_writes_outcome_with_bound_strategy(
    tmp_path: Path,
) -> None:
    store = attr.get_strategy_attribution_store()
    store.bind_fill(
        strategy_id="trend_continuation",
        engine="soe",
        ticket=9100,
        position_id=9100,
        contributors=["momentum_scalping"],
        broker_login=12479147,
    )
    evidence = BrokerExitEvidence(
        position_id=9100,
        symbol="XAUUSD",
        exit_deal_id=99100,
        entry_deal_id=99099,
        exit_price=4050.0,
        entry_price=4048.0,
        exit_time=_WHEN.isoformat(),
        entry_time=None,
        volume=0.01,
        profit=-2.0,
        commission=0.0,
        swap=0.0,
        net_pnl=-2.0,
        close_reason="[sl 4050.0]",
        side="sell",
        hold_seconds=60.0,
        entry_comment="ite:v1:S:abcdef012345",
    )
    result = record_broker_confirmed_close(
        evidence=evidence,
        strategy_id=None,
        ledger=reset_close_attribution_ledger_for_tests(tmp_path / "led2.json"),
    )
    assert result["strategy_id"] == "trend_continuation"
    assert result["outcome_status"] == "created"
    rows = outcomes.list_trade_outcomes(broker_login=12479147)
    assert len(rows) == 1
    assert rows[0].strategy_id == "trend_continuation"
    assert "momentum_scalping" in rows[0].contributors
    assert rows[0].attribution_confidence == "bound_five_pack"
    assert rows[0].costs_complete is True


def test_ite_entry_without_binding_stays_unattributed(tmp_path: Path) -> None:
    evidence = BrokerExitEvidence(
        position_id=9200,
        symbol="XAUUSD",
        exit_deal_id=99200,
        entry_deal_id=99199,
        exit_price=4050.0,
        entry_price=4048.0,
        exit_time=_WHEN.isoformat(),
        entry_time=None,
        volume=0.01,
        profit=-1.5,
        commission=0.0,
        swap=0.0,
        net_pnl=-1.5,
        close_reason="[sl 4050.0]",
        side="sell",
        hold_seconds=30.0,
        entry_comment="ite:v1:H:deadbeefcafe",
    )
    result = record_broker_confirmed_close(
        evidence=evidence,
        ledger=reset_close_attribution_ledger_for_tests(tmp_path / "led3.json"),
    )
    assert result["strategy_id"] is None
    rows = outcomes.list_trade_outcomes()
    assert rows[0].strategy_id is None
    assert rows[0].attribution_confidence == "unknown"


def test_five_pack_scorecard_and_post182_monitor() -> None:
    outcomes.record_trade_outcome(
        position_id=1,
        exit_deal_id=1,
        net_pnl=2.0,
        strategy_id="smc_scalping",
        side="BUY",
        closed_at=_WHEN,
        broker_login=12479147,
        costs_complete=True,
        commission=0.0,
        swap=0.0,
        attribution_confidence="bound_five_pack",
    )
    outcomes.record_trade_outcome(
        position_id=2,
        exit_deal_id=2,
        net_pnl=-3.0,
        strategy_id=None,
        side="SELL",
        closed_at=_WHEN,
        broker_login=12479147,
        costs_complete=False,
        attribution_confidence="unknown",
    )
    rows = outcomes.list_trade_outcomes(broker_login=12479147, period="post_pr182")
    cards = perf.build_five_pack_scorecards(rows, account=12479147)
    smc = next(c for c in cards if c["strategy_id"] == "smc_scalping")
    assert smc["closed_trades"] == 1
    assert smc["net_pnl"] == 2.0
    unknown = next(c for c in cards if c["strategy_id"] is None)
    assert unknown["closed_trades"] == 1
    assert unknown["classification"] == "Insufficient attribution"
    mon = perf.build_post182_performance_monitor(broker_login=12479147)
    assert mon["post_pr182"]["n"] == 2
    assert mon["post_pr182"]["incomplete_cost_records"] == 1
    assert mon["features"]["changes_trading_decisions"] is False


def test_restart_restore_api_keeps_binding(tmp_path: Path) -> None:
    path = tmp_path / "durable_attr.json"
    attr.reset_strategy_attribution_store_for_tests(path)
    store = attr.get_strategy_attribution_store()
    store.bind_fill(
        strategy_id="breakout_scalping",
        engine="soe",
        ticket=9300,
        position_id=9300,
    )
    assert path.exists()
    reloaded = attr.StrategyAttributionStore(path=path)
    hit = reloaded.resolve(ticket=9300)
    assert hit is not None
    assert hit.strategy_id == "breakout_scalping"
