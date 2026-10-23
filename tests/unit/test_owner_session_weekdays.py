"""Owner session is Monday-Friday 07:00-17:00 UTC; no entries at weekends.

Owner 2026-10-23: the 07-17 window checked the clock only, so the robot
could auto-resume on Saturday/Sunday mornings (market closed anyway).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.mark.parametrize(
    ("moment", "inside"),
    [
        (datetime(2026, 10, 23, 16, 59, tzinfo=UTC), True),  # Friday
        (datetime(2026, 10, 23, 17, 0, tzinfo=UTC), False),  # Friday close
        (datetime(2026, 10, 24, 10, 0, tzinfo=UTC), False),  # Saturday
        (datetime(2026, 10, 25, 10, 0, tzinfo=UTC), False),  # Sunday
        (datetime(2026, 10, 26, 6, 59, tzinfo=UTC), False),  # Monday pre-open
        (datetime(2026, 10, 26, 7, 0, tzinfo=UTC), True),  # Monday open
    ],
)
def test_session_is_weekdays_07_to_17_utc(moment: datetime, inside: bool) -> None:
    assert ol.in_owner_session(moment) is inside


def test_naive_and_offset_clocks_use_utc() -> None:
    # Sunday 23:30 UTC is Monday 02:30 at +03:00: still outside the session.
    from datetime import timedelta, timezone

    plus3 = timezone(timedelta(hours=3))
    assert not ol.in_owner_session(datetime(2026, 10, 26, 2, 30, tzinfo=plus3))
    assert ol.in_owner_session(datetime(2026, 10, 26, 10, 0))  # naive = UTC


def test_weekend_entry_is_refused_by_the_owner_guard() -> None:
    reasons = ol.evaluate_owner_entry(
        symbol="XAUUSD",
        side="SELL",
        volume=D("0.01"),
        entry=D("4000.00"),
        stop_loss=D("4002.00"),
        take_profit=D("3996.00"),
        spread=D("0.20"),
        contract_size=D("100"),
        equity=D("32.88"),
        now=datetime(2026, 10, 24, 10, 0, tzinfo=UTC),
    )
    assert any(r.startswith("OWNER_SESSION") for r in reasons), reasons
    assert any("Mon-Fri" in r for r in reasons)


def test_weekend_blocks_auto_resume() -> None:
    from app.application.services import live_trading_control_service as svc

    facts = {
        "gateway_online": True,
        "mt5_connected": True,
        "mt5_attached": True,
        "ownership": "OWNED",
        "account_available": True,
        "account_login": 50001234,
        "equity": D("32.88"),
        "balance": D("32.88"),
    }
    blockers = svc.autonomous_resume_blockers(
        facts, now=datetime(2026, 10, 24, 10, 0, tzinfo=UTC)
    )
    assert "outside_session" in blockers
