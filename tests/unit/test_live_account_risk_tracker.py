"""Unit tests — persisted peak equity + MT5 deal daily PnL."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.live_account_risk_tracker import (
    LiveAccountRiskTracker,
    reset_live_account_risk_tracker_for_tests,
)
from app.domain.entities.mt5_portfolio import MT5Deal


def _deal(
    *,
    profit: str,
    when: datetime,
    volume: str = "0.01",
    commission: str = "0",
    swap: str = "0",
    ticket: int = 1,
    deal_type: str = "entry_out",
) -> MT5Deal:
    return MT5Deal(
        ticket=ticket,
        order_ticket=ticket,
        symbol="XAUUSD",
        side="buy",
        volume=Decimal(volume),
        price=Decimal("2300"),
        profit=Decimal(profit),
        commission=Decimal(commission),
        swap=Decimal(swap),
        deal_type=deal_type,
        time=when,
    )


@pytest.fixture(autouse=True)
def _reset_tracker() -> None:
    reset_live_account_risk_tracker_for_tests()


@pytest.mark.unit
@pytest.mark.trading_core
class TestLiveAccountRiskTracker:
    def test_peak_equity_persists_and_rises(self, tmp_path: Path) -> None:
        path = tmp_path / "peak.json"
        tracker = LiveAccountRiskTracker(persist_path=path)
        p1 = tracker.observe_equity(login=1001, equity=Decimal("10000"))
        assert p1 == Decimal("10000")
        p2 = tracker.observe_equity(login=1001, equity=Decimal("9500"))
        assert p2 == Decimal("10000")
        p3 = tracker.observe_equity(login=1001, equity=Decimal("11000"))
        assert p3 == Decimal("11000")

        # Reload from disk — HWM must survive restart.
        tracker2 = LiveAccountRiskTracker(persist_path=path)
        assert tracker2.peak_for(1001) == Decimal("11000")

    def test_daily_pnl_from_today_deals_only(self) -> None:
        now = datetime(2026, 7, 22, 15, 0, tzinfo=UTC)
        today = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
        yesterday = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
        deals = [
            _deal(profit="-50", when=today, ticket=11),
            _deal(profit="20", when=today, commission="-2", ticket=12),
            _deal(profit="-999", when=yesterday, ticket=13),
        ]
        pnl = LiveAccountRiskTracker.daily_pnl_from_deals(deals, now=now)
        assert pnl == Decimal("-32")

    def test_resolve_for_risk_uses_deals_not_floating(self, tmp_path: Path) -> None:
        tracker = LiveAccountRiskTracker(persist_path=tmp_path / "r.json")
        now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
        deals = [_deal(profit="-75", when=now)]
        peak, daily = tracker.resolve_for_risk(
            login=42,
            equity=Decimal("9900"),
            balance=Decimal("10000"),
            deals=deals,
            now=now,
        )
        assert peak == Decimal("10000")  # lifted by balance observe
        assert daily == Decimal("-75")

    def test_duplicate_ticket_is_not_double_counted(self) -> None:
        now = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
        deals = [
            _deal(profit="-25.11", when=now, ticket=88),
            _deal(profit="-25.11", when=now, ticket=88),
        ]
        pnl = LiveAccountRiskTracker.daily_pnl_from_deals(deals, now=now)
        assert pnl == Decimal("-25.11")

    def test_balance_and_zero_volume_deposits_are_excluded(self) -> None:
        now = datetime(2026, 8, 27, 15, 0, tzinfo=UTC)
        deals = [
            _deal(profit="-25.11", when=now, ticket=1),
            _deal(
                profit="-100",
                when=now,
                ticket=2,
                volume="0",
                deal_type="balance",
            ),
        ]
        pnl = LiveAccountRiskTracker.daily_pnl_from_deals(deals, now=now)
        assert pnl == Decimal("-25.11")

    def test_verified_deposit_slices_pre_deposit_loss_from_risk(self) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        pre = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
        dep_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
        deals = [
            _deal(profit="-200", when=pre, ticket=11),
            _deal(
                profit="400",
                when=dep_at,
                ticket=22,
                volume="0",
                deal_type="balance",
            ),
            _deal(profit="-10", when=now, ticket=33),
        ]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(
            deals, now=now, ending_balance=Decimal("500")
        )
        assert resolved["session_trade_pnl"] == Decimal("-210")
        assert resolved["pre_deposit_trade_pnl"] == Decimal("-200")
        assert resolved["post_deposit_trade_pnl"] == Decimal("-10")
        assert resolved["risk_daily_pnl"] == Decimal("-10")
        assert resolved["new_capital_detected"] is True
        baseline = resolved["capital_baseline"]
        assert baseline["deposit_amount"] == "400"
        assert baseline["broker_deal_ticket"] == 22
        assert baseline["utc_date"] == "2026-09-01"
        assert baseline["baseline_source"] == "mt5_balance_credit_deal"
        assert baseline["balance_before"] == "110"
        assert baseline["balance_after"] == "510"
        assert (
            LiveAccountRiskTracker.daily_pnl_from_deals(
                deals, now=now, ending_balance=Decimal("500")
            )
            == Decimal("-10")
        )

    def test_unverified_balance_increase_is_not_a_deposit(self) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        deals = [_deal(profit="-80", when=now, ticket=1)]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(
            deals, now=now, ending_balance=Decimal("500")
        )
        assert resolved["new_capital_detected"] is False
        assert resolved["capital_baseline"] is None
        assert resolved["risk_daily_pnl"] == Decimal("-80")
        assert resolved["session_trade_pnl"] == Decimal("-80")

    def test_multiple_deposits_use_latest_utc_day_baseline(self) -> None:
        now = datetime(2026, 9, 1, 18, 0, tzinfo=UTC)
        deals = [
            _deal(profit="-50", when=datetime(2026, 9, 1, 9, 0, tzinfo=UTC), ticket=1),
            _deal(
                profit="100",
                when=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
                ticket=2,
                volume="0",
                deal_type="balance",
            ),
            _deal(profit="-20", when=datetime(2026, 9, 1, 11, 0, tzinfo=UTC), ticket=3),
            _deal(
                profit="200",
                when=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
                ticket=4,
                volume="0",
                deal_type="credit",
            ),
            _deal(profit="-5", when=datetime(2026, 9, 1, 13, 0, tzinfo=UTC), ticket=5),
        ]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(
            deals, now=now, ending_balance=Decimal("225")
        )
        assert resolved["capital_baseline"]["broker_deal_ticket"] == 4
        assert resolved["pre_deposit_trade_pnl"] == Decimal("-70")
        assert resolved["post_deposit_trade_pnl"] == Decimal("-5")
        assert resolved["risk_daily_pnl"] == Decimal("-5")

    def test_duplicate_deposit_ticket_is_not_double_baselined(self) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        dep = _deal(
            profit="300",
            when=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            ticket=77,
            volume="0",
            deal_type="balance",
        )
        deals = [
            _deal(profit="-40", when=datetime(2026, 9, 1, 10, 0, tzinfo=UTC), ticket=1),
            dep,
            dep,
            _deal(profit="-1", when=now, ticket=2),
        ]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(
            deals, now=now, ending_balance=Decimal("259")
        )
        assert resolved["capital_baseline"]["deposit_amount"] == "300"
        assert resolved["risk_daily_pnl"] == Decimal("-1")

    def test_yesterday_deposit_does_not_slice_today_trades(self) -> None:
        now = datetime(2026, 9, 1, 1, 0, tzinfo=UTC)
        deals = [
            _deal(
                profit="500",
                when=datetime(2026, 8, 31, 23, 0, tzinfo=UTC),
                ticket=9,
                volume="0",
                deal_type="balance",
            ),
            _deal(profit="-30", when=now, ticket=10),
        ]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(deals, now=now)
        assert resolved["new_capital_detected"] is False
        assert resolved["risk_daily_pnl"] == Decimal("-30")

    def test_bonus_and_charge_are_not_verified_deposits(self) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        deals = [
            _deal(profit="-40", when=now, ticket=1),
            _deal(
                profit="80",
                when=now,
                ticket=2,
                volume="0",
                deal_type="bonus",
            ),
            _deal(
                profit="-5",
                when=now,
                ticket=3,
                volume="0",
                deal_type="charge",
            ),
        ]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(deals, now=now)
        assert resolved["new_capital_detected"] is False
        assert resolved["risk_daily_pnl"] == Decimal("-40")

    def test_numeric_mt5_balance_type_is_verified_deposit(self) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        from types import SimpleNamespace

        deals = [
            _deal(profit="-12", when=datetime(2026, 9, 1, 10, 0, tzinfo=UTC), ticket=1),
            SimpleNamespace(
                ticket=2,
                type=2,
                deal_type=None,
                volume=0,
                profit=100,
                commission=0,
                swap=0,
                time=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            ),
        ]
        resolved = LiveAccountRiskTracker.session_pnl_resolution(deals, now=now)
        assert resolved["new_capital_detected"] is True
        assert resolved["risk_daily_pnl"] == Decimal("0")

    def test_missing_broker_history_does_not_invent_a_deposit(self) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        resolved = LiveAccountRiskTracker.session_pnl_resolution(
            [], now=now, ending_balance=Decimal("999")
        )
        assert resolved["new_capital_detected"] is False
        assert resolved["risk_daily_pnl"] == Decimal("0")
        assert resolved["session_trade_pnl"] == Decimal("0")

    def test_restart_recomputes_slice_from_live_deals(self, tmp_path: Path) -> None:
        now = datetime(2026, 9, 1, 16, 0, tzinfo=UTC)
        deals = [
            _deal(
                profit="-200",
                when=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
                ticket=1,
            ),
            _deal(
                profit="400",
                when=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
                ticket=2,
                volume="0",
                deal_type="balance",
            ),
        ]
        tracker = LiveAccountRiskTracker(persist_path=tmp_path / "r.json")
        _peak, daily = tracker.resolve_for_risk(
            login=12,
            equity=Decimal("400"),
            balance=Decimal("400"),
            deals=deals,
            now=now,
        )
        assert daily == Decimal("0")
        tracker2 = LiveAccountRiskTracker(persist_path=tmp_path / "r.json")
        _peak2, daily2 = tracker2.resolve_for_risk(
            login=12,
            equity=Decimal("400"),
            balance=Decimal("400"),
            deals=deals,
            now=now,
        )
        assert daily2 == Decimal("0")
        assert tracker2.peak_for(12) == Decimal("400")
