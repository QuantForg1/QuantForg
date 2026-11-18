"""Owner entry window: Monday-Friday, 07:00 (inclusive) to 17:00 (exclusive) UTC.

Owner baseline 2026-11-16. Broker-closed, unknown weekend, and the risk
limits still block on their own. Closes and SL/TP management are never
gated by this clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from app.domain.institutional_trading import owner_live_limits as ol
from app.domain.institutional_trading.auto_trading import (
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from tests.unit.test_auto_trading_safety import _all_pass_facts

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_INSIDE = (
    datetime(2026, 10, 26, 7, 0, tzinfo=UTC),  # Monday open edge
    datetime(2026, 10, 26, 12, 30, tzinfo=UTC),  # Monday midday
    datetime(2026, 10, 23, 16, 59, tzinfo=UTC),  # Friday last minute
    datetime(2026, 10, 22, 10, 0, tzinfo=UTC),  # Thursday London
)

_OUTSIDE = (
    datetime(2026, 10, 26, 0, 0, tzinfo=UTC),  # Monday 00:00
    datetime(2026, 10, 26, 6, 59, tzinfo=UTC),  # Monday pre-open
    datetime(2026, 10, 23, 17, 0, tzinfo=UTC),  # Friday close edge
    datetime(2026, 10, 23, 23, 59, tzinfo=UTC),  # Friday 23:59
    datetime(2026, 10, 24, 10, 0, tzinfo=UTC),  # Saturday
    datetime(2026, 10, 25, 12, 0, tzinfo=UTC),  # Sunday
)


def _valid(**kw: object) -> list[str]:
    base: dict[str, object] = {
        "symbol": "XAUUSD",
        "side": "SELL",
        "volume": D("0.01"),
        "entry": D("4000.00"),
        "stop_loss": D("4002.00"),
        "take_profit": D("3996.00"),
        "spread": D("0.20"),
        "contract_size": D("100"),
        "equity": D("32.88"),
        "commission": D("0"),
        "daily": ol.DailyLossContext(
            trusted=True, balance=D("32.88"), equity=D("32.88")
        ),
    }
    base.update(kw)
    return ol.evaluate_owner_entry(**base)  # type: ignore[arg-type]


def _codes(reasons: list[str]) -> set[str]:
    return {r.split(":", 1)[0] for r in reasons}


def test_reported_window_is_the_owner_desk() -> None:
    from app.domain.institutional_trading.runtime_policy import (
        active_trading_window,
    )

    # Default for a new profile is 24/5; the installed (former) profile is
    # Mon-Fri 07:00-17:00 UTC.
    assert f"{ol.OWNER_SESSION_START_UTC:%H:%M}" == "00:00"
    assert frozenset({0, 1, 2, 3, 4}) == ol.OWNER_SESSION_WEEKDAYS
    days, start, end = active_trading_window()
    assert (f"{start:%H:%M}", f"{end:%H:%M}") == ("07:00", "17:00")
    assert frozenset({0, 1, 2, 3, 4}) == days


@pytest.mark.parametrize("moment", _INSIDE)
def test_session_gate_accepts_the_owner_window(moment: datetime) -> None:
    assert ol.in_owner_session(moment) is True
    reasons = _valid(now=moment)
    assert reasons == [], reasons


@pytest.mark.parametrize("moment", _OUTSIDE)
def test_session_gate_rejects_outside_the_owner_window(moment: datetime) -> None:
    assert ol.in_owner_session(moment) is False
    assert "OWNER_SESSION" in _codes(_valid(now=moment))


def test_naive_and_offset_clocks_use_utc() -> None:
    plus3 = timezone(timedelta(hours=3))
    # Monday 10:30 at +03:00 is 07:30 UTC: inside. 09:30 at +03:00 is 06:30.
    assert ol.in_owner_session(datetime(2026, 10, 26, 10, 30, tzinfo=plus3))
    assert not ol.in_owner_session(datetime(2026, 10, 26, 9, 30, tzinfo=plus3))
    assert ol.in_owner_session(datetime(2026, 10, 26, 10, 0))


@pytest.mark.parametrize("moment", _INSIDE)
def test_risk_limits_still_reject_inside_the_window(moment: datetime) -> None:
    assert "OWNER_MAX_SPREAD" in _codes(_valid(now=moment, spread=D("0.46")))
    assert "OWNER_GOLD_ONLY" in _codes(_valid(now=moment, symbol="EURUSD"))
    assert "OWNER_GOLD_ONLY" in _codes(_valid(now=moment, symbol="XAUJPY"))
    assert "OWNER_SL_REQUIRED" in _codes(_valid(now=moment, stop_loss=None))
    low_rr = _valid(now=moment, take_profit=D("3997.00"))
    assert "OWNER_MIN_RR" in _codes(low_rr)
    wide = _valid(
        now=moment,
        stop_loss=D("4010.00"),
        take_profit=D("3970.00"),
        equity=D("50"),
    )
    assert "OWNER_SL_RISK" in _codes(wide)


def test_daily_loss_cap_blocks_above_25_percent() -> None:
    from app.domain.institutional_trading.runtime_policy import (
        active_daily_loss_pct,
        active_max_planned_risk_pct,
    )

    assert D("25.0") == active_daily_loss_pct()
    assert D("9.0") == active_max_planned_risk_pct()
    assert ol.daily_loss_exceeded(daily_pnl=D("-12.51"), base_now=D("37.49")) is True
    assert ol.daily_loss_exceeded(daily_pnl=D("-12.50"), base_now=D("37.50")) is False


def test_broker_closed_still_blocks_outside_the_former_window() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    for session in ("tokyo", "new_york", "off_hours"):
        result = evaluate_auto_trade_safety(
            policy,
            _all_pass_facts(session=session, broker_session_open=False),
        )
        assert result.allowed is False
        assert any("BROKER_SESSION_CLOSED" in r for r in result.failed_reasons)


def test_unknown_broker_does_not_invent_a_weekend_open() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running")
    result = evaluate_auto_trade_safety(
        policy,
        _all_pass_facts(session="off_hours", broker_session_open=None),
    )
    assert result.allowed is False
    assert any("off_hours" in r for r in result.failed_reasons)


def test_auto_resume_waits_for_the_owner_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services import live_trading_control_service as svc

    monkeypatch.setattr(svc, "_unknown_positions", lambda: [])
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
    for moment in _INSIDE:
        blockers = svc.autonomous_resume_blockers(facts, now=moment)
        assert "outside_session" not in blockers
    for moment in _OUTSIDE:
        blockers = svc.autonomous_resume_blockers(facts, now=moment)
        assert "outside_session" in blockers
