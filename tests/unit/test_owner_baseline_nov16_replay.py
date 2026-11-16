"""Replay of the 20 real Weltrade entries opened on 16 November 2026.

LIVE ran on the pre-#295 code (20% per trade / 48% daily / RR 0.20 / any hour).
Every one of these entries must be rejected by the 2026-11-16 owner baseline:
each planned risk was above 9% of equity, most had RR below 1.5, twelve
opened before 07:00 UTC, and the daily budget/stop fires before the last ones.
Prices, stops, spreads and P/L come from live_trade_journal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

START_BALANCE = D("20.69")
# side, entry, stop, take profit, spread, opened (UTC), closed (UTC), P/L
# fmt: off
TRADES = [
    ("BUY", "3891.587", "3889.649", "3897.283", "0.444", "02:16:33", "02:16:51", "-1.96"),  # noqa: E501
    ("SELL", "3879.433", "3881.648", "3877.353", "0.444", "04:34:04", "04:36:08", "-2.43"),  # noqa: E501
    ("SELL", "3874.833", "3877.386", "3872.743", "0.384", "05:00:12", "05:01:40", "2.09"),  # noqa: E501
    ("SELL", "3871.353", "3873.949", "3869.353", "0.424", "05:14:55", "05:19:59", "2.00"),  # noqa: E501
    ("SELL", "3871.233", "3873.804", "3869.353", "0.444", "05:23:32", "05:26:31", "1.88"),  # noqa: E501
    ("SELL", "3870.383", "3872.229", "3868.843", "0.444", "05:27:14", "05:27:41", "-1.94"),  # noqa: E501
    ("SELL", "3869.563", "3872.127", "3867.833", "0.384", "05:30:23", "05:31:43", "1.73"),  # noqa: E501
    ("SELL", "3869.193", "3872.157", "3867.833", "0.444", "05:42:40", "05:44:00", "-3.21"),  # noqa: E501
    ("SELL", "3871.903", "3873.563", "3869.353", "0.444", "06:06:41", "06:21:53", "2.55"),  # noqa: E501
    ("SELL", "3872.973", "3874.964", "3872.523", "0.444", "06:40:43", "06:45:36", "0.45"),  # noqa: E501
    ("SELL", "3871.603", "3873.380", "3871.373", "0.444", "06:47:16", "06:48:02", "-1.91"),  # noqa: E501
    ("SELL", "3871.053", "3873.197", "3870.393", "0.444", "06:49:52", "06:52:30", "0.66"),  # noqa: E501
    ("SELL", "3868.093", "3869.619", "3863.933", "0.424", "07:08:34", "07:08:52", "-1.53"),  # noqa: E501
    ("SELL", "3869.223", "3871.711", "3867.833", "0.444", "07:33:22", "07:34:13", "1.39"),  # noqa: E501
    ("SELL", "3866.243", "3869.587", "3863.933", "0.444", "07:35:12", "07:36:57", "2.31"),  # noqa: E501
    ("SELL", "3866.723", "3869.750", "3865.963", "0.434", "07:44:19", "07:45:05", "0.76"),  # noqa: E501
    ("SELL", "3851.323", "3854.798", "3847.993", "0.434", "08:14:40", "08:16:11", "-3.70"),  # noqa: E501
    ("SELL", "3846.243", "3849.329", "3835.303", "0.434", "08:36:24", "08:55:55", "-3.39"),  # noqa: E501
    ("SELL", "3851.503", "3853.327", "3847.713", "0.374", "09:23:18", "09:25:46", "-1.82"),  # noqa: E501
    ("SELL", "3853.883", "3856.145", "3851.433", "0.344", "09:45:20", "09:47:43", "-2.32"),  # noqa: E501
]
# fmt: on


def _at(hms: str) -> datetime:
    return datetime.fromisoformat(f"2026-11-16T{hms}").replace(tzinfo=UTC)


def _codes(index: int) -> set[str]:
    side, entry, stop, tp, spread, opened, _closed, _pnl = TRADES[index]
    now = _at(opened)
    realized = sum((D(t[7]) for t in TRADES if _at(t[6]) <= now), start=D("0"))
    balance = START_BALANCE + realized
    daily = ol.DailyLossContext(
        trusted=True, realized_pnl=realized, balance=balance, equity=balance
    )
    violations = ol.evaluate_owner_entry(
        symbol="XAUUSD",
        side=side,
        volume=D("0.01"),
        entry=D(entry),
        stop_loss=D(stop),
        take_profit=D(tp),
        spread=D(spread),
        contract_size=D("100"),
        equity=balance,
        commission=D("0"),
        now=now,
        daily=daily,
    )
    return {v.split(":")[0] for v in violations}


@pytest.mark.parametrize("index", range(len(TRADES)))
def test_every_november_16_entry_is_rejected(index: int) -> None:
    codes = _codes(index)
    assert codes, f"trade {index + 1} would have been allowed"
    assert "OWNER_SL_RISK" in codes  # each one risked more than 9% of equity


def test_entries_before_07_utc_are_outside_the_session() -> None:
    early = [i for i, t in enumerate(TRADES) if _at(t[5]).hour < 7]
    assert len(early) == 12
    assert all("OWNER_SESSION" in _codes(i) for i in early)


def test_daily_stop_fires_once_the_loss_passes_25_percent() -> None:
    assert "OWNER_DAILY_STOP" in _codes(len(TRADES) - 1)
