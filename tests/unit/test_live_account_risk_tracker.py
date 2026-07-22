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
) -> MT5Deal:
    return MT5Deal(
        ticket=1,
        order_ticket=1,
        symbol="XAUUSD",
        side="buy",
        volume=Decimal(volume),
        price=Decimal("2300"),
        profit=Decimal(profit),
        commission=Decimal(commission),
        swap=Decimal(swap),
        deal_type="entry_out",
        time=when,
    )


@pytest.fixture(autouse=True)
def _reset_tracker() -> None:
    reset_live_account_risk_tracker_for_tests()


@pytest.mark.unit
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
            _deal(profit="-50", when=today),
            _deal(profit="20", when=today, commission="-2"),
            _deal(profit="-999", when=yesterday),
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
