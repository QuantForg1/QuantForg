"""Phase 3 — household aggregation, exposure, risk, attribution, honesty."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.application.services.institutional_execution_engine import (
    broker_submit_block_reason,
)
from app.domain.entities.mt5_order import LotSize, OrderIntent
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.order import OrderSide, OrderType
from app.domain.institutional_trading.operations.live_prefs_tighten import (
    tighten_risk_config_from_effective,
)
from app.domain.portfolio_household.aggregation import (
    AccountMetricSlice,
    PositionSlice,
    aggregate_household,
    classify_status,
    dedupe_positions,
)
from app.domain.portfolio_household.emergency_stops import EmergencyStopStore
from app.domain.portfolio_household.exposure import rollup_exposure
from app.domain.portfolio_household.performance import (
    ClosedTrade,
    build_performance_report,
    performance_to_csv,
)
from app.domain.portfolio_household.risk_allocation import (
    evaluate_household_risk,
    household_new_entry_block_reason,
)


def test_classify_status_honesty() -> None:
    now = datetime.now(UTC)
    assert (
        classify_status(
            has_live=True, as_of=now, connected=True, ownership_verified=True
        )
        == "live"
    )
    assert (
        classify_status(
            has_live=False,
            as_of=now - timedelta(hours=2),
            connected=True,
            ownership_verified=True,
            now=now,
        )
        == "stale"
    )
    assert (
        classify_status(
            has_live=False, as_of=None, connected=False, ownership_verified=True
        )
        == "disconnected"
    )
    assert (
        classify_status(
            has_live=False, as_of=None, connected=None, ownership_verified=False
        )
        == "unverified"
    )


def test_missing_accounts_never_coerced_to_zero() -> None:
    uid = uuid4()
    accounts = [
        AccountMetricSlice(
            broker_account_id="a1",
            broker_code="weltrade",
            broker_name="Weltrade",
            server="Weltrade-Real",
            login="1",
            currency="USD",
            data_status="live",
            as_of=datetime.now(UTC),
            balance=Decimal("100"),
            equity=Decimal("110"),
            floating_pnl=Decimal("10"),
        ),
        AccountMetricSlice(
            broker_account_id="a2",
            broker_code="exness",
            broker_name="Exness",
            server=None,
            login="2",
            currency=None,
            data_status="unavailable",
            as_of=None,
            note="no_readable_snapshot",
        ),
    ]
    hh = aggregate_household(user_id=uid, accounts=accounts, positions=[])
    assert hh.totals.balance == Decimal("100")
    assert hh.totals.equity == Decimal("110")
    assert hh.totals.accounts_excluded == 1
    assert hh.accounts[1].equity is None
    assert hh.accounts[1].balance is None


def test_fx_unavailable_excludes_cross_currency() -> None:
    uid = uuid4()
    accounts = [
        AccountMetricSlice(
            broker_account_id="a1",
            broker_code="weltrade",
            broker_name="W",
            server=None,
            login="1",
            currency="USD",
            data_status="live",
            as_of=datetime.now(UTC),
            equity=Decimal("100"),
            balance=Decimal("100"),
        ),
        AccountMetricSlice(
            broker_account_id="a2",
            broker_code="ic",
            broker_name="IC",
            server=None,
            login="2",
            currency="EUR",
            data_status="cached",
            as_of=datetime.now(UTC),
            equity=Decimal("50"),
            balance=Decimal("50"),
        ),
    ]
    hh = aggregate_household(
        user_id=uid,
        accounts=accounts,
        positions=[],
        display_currency="USD",
        verified_fx=None,
    )
    assert hh.totals.equity == Decimal("100")
    assert hh.totals.accounts_excluded == 1
    assert hh.totals.conversion_status in {"unavailable", "native_only", "ok"}


def test_position_dedup() -> None:
    positions = [
        PositionSlice("a", "a", "w", 1, "XAUUSD", "buy", Decimal("0.01"), Decimal("1")),
        PositionSlice("a", "a", "w", 1, "XAUUSD", "buy", Decimal("0.01"), Decimal("1")),
        PositionSlice(
            "a", "a", "w", 2, "XAUUSD", "sell", Decimal("0.02"), Decimal("-1")
        ),
    ]
    out = dedupe_positions(positions)
    assert len(out) == 2


def test_exposure_and_overlap() -> None:
    positions = [
        PositionSlice(
            "a1", "a1", "weltrade", 1, "XAUUSD", "buy", Decimal("0.1"), Decimal("2")
        ),
        PositionSlice(
            "a2", "a2", "xm", 2, "XAUUSD", "sell", Decimal("0.05"), Decimal("-1")
        ),
    ]
    exp = rollup_exposure(positions)
    assert exp.total_long_volume == Decimal("0.1")
    assert exp.total_short_volume == Decimal("0.05")
    assert any(o["symbol"] == "XAUUSD" for o in exp.overlapping)


def test_performance_excludes_unconfirmed() -> None:
    trades = [
        ClosedTrade(
            trade_id="1",
            symbol="XAUUSD",
            side="buy",
            pnl=Decimal("10"),
            commission=None,
            swap=None,
            opened_at=None,
            closed_at=datetime.now(UTC),
            hold_seconds=60,
            strategy="alpha",
            broker_code="weltrade",
            account_key="a",
            signal_id="sig-1",
            order_ticket=1,
            position_ticket=1,
            session="london",
            confirmed=True,
        ),
        ClosedTrade(
            trade_id="2",
            symbol="XAUUSD",
            side="sell",
            pnl=Decimal("-5"),
            commission=None,
            swap=None,
            opened_at=None,
            closed_at=None,
            hold_seconds=None,
            strategy="alpha",
            broker_code="weltrade",
            account_key="a",
            signal_id=None,
            order_ticket=None,
            position_ticket=None,
            session=None,
            confirmed=False,
        ),
    ]
    report = build_performance_report(trades)
    assert report.trades_considered == 1
    assert report.trades_excluded_unconfirmed == 1
    assert report.overall.net_profit == Decimal("10")
    csv = performance_to_csv(report)
    assert "password" not in csv.lower()
    assert "token" not in csv.lower()
    assert "sig-1" in csv


def test_household_risk_blocks_when_aggregate_exceeded() -> None:
    accounts = [
        AccountMetricSlice(
            broker_account_id="a1",
            broker_code="weltrade",
            broker_name="W",
            server=None,
            login="1",
            currency="USD",
            data_status="live",
            as_of=datetime.now(UTC),
            equity=Decimal("100"),
            floating_pnl=Decimal("-40"),
        )
    ]
    check = evaluate_household_risk(
        accounts=accounts,
        positions=[],
        effective={"aggregate_open_risk_pct": "30"},
        proposed_risk_pct=Decimal("5"),
    )
    assert check.allowed is False
    assert check.block_reason and "HOUSEHOLD_RISK" in check.block_reason


def test_emergency_stop_blocks_new_entries_only() -> None:
    from app.domain.portfolio_household.emergency_stops import get_emergency_stop_store

    store = get_emergency_stop_store()
    uid = uuid4()
    store.arm(scope="user", scope_id=uid, reason="test", actor_user_id=uid)
    reason = household_new_entry_block_reason(user_id=uid)
    assert reason and "HOUSEHOLD_STOP" in reason
    store.disarm(scope="user", scope_id=uid, reason="clear", actor_user_id=uid)
    assert household_new_entry_block_reason(user_id=uid) is None


def test_live_prefs_tighten_aggregate_open_risk() -> None:
    cfg = RiskEngineConfig(
        max_total_exposure_pct=Decimal("80"),
        max_correlated_exposure_pct=Decimal("40"),
    )
    out = tighten_risk_config_from_effective(cfg, {"aggregate_open_risk_pct": "25"})
    assert out.max_total_exposure_pct == Decimal("25")
    assert out.max_correlated_exposure_pct == Decimal("25")
    # Cannot loosen
    loose = tighten_risk_config_from_effective(cfg, {"aggregate_open_risk_pct": "90"})
    assert loose.max_total_exposure_pct == Decimal("80")


def test_broker_submit_block_respects_household_stop(monkeypatch) -> None:
    from app.domain.portfolio_household import emergency_stops as es

    store = EmergencyStopStore()
    uid = uuid4()
    store.arm(scope="user", scope_id=uid, reason="halt", actor_user_id=uid)
    monkeypatch.setattr(es, "_STORE", store)
    monkeypatch.setattr(
        "app.domain.portfolio_household.risk_allocation.get_emergency_stop_store",
        lambda: store,
    )

    # Force kill switch clear / orders allowed path by stubbing dependencies.
    class _KS:
        enabled = False

    monkeypatch.setattr(
        "app.domain.institutional_trading.execution.kill_switch.KillSwitch",
        lambda **_kwargs: _KS(),
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.operations.control_plane.get_control_plane",
        lambda: object(),
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.live_trading_control.orders_may_submit",
        lambda _s: True,
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.live_trading_control.get_live_trading_controller",
        lambda: type("C", (), {"snapshot_state": staticmethod(lambda: {})})(),
    )

    intent = OrderIntent(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )
    block = broker_submit_block_reason(intent, user_id=uid)
    assert block and "HOUSEHOLD_STOP" in block

    # Manage path still allowed past household (risk-reducing)
    manage = OrderIntent(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
        oms_kind="close",
    )
    # Risk-reducing close returns None before household stop.
    assert broker_submit_block_reason(manage, user_id=uid) is None
