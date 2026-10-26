"""The owner clock is the full UTC day, seven days a week.

Owner 2026-10-26: 07:00-17:00 Monday-Friday no longer blocks a valid entry.
Broker-closed, unknown weekend, and the risk limits still do.
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

# Times the retired desk window rejected, plus the old open and close edges.
_FULL_DAY = (
    datetime(2026, 10, 26, 0, 0, tzinfo=UTC),  # Monday 00:00
    datetime(2026, 10, 26, 3, 0, tzinfo=UTC),  # Monday 03:00
    datetime(2026, 10, 26, 6, 59, tzinfo=UTC),  # Monday pre-London
    datetime(2026, 10, 26, 7, 0, tzinfo=UTC),  # former open
    datetime(2026, 10, 23, 16, 59, tzinfo=UTC),  # Friday 16:59
    datetime(2026, 10, 23, 17, 0, tzinfo=UTC),  # former close
    datetime(2026, 10, 23, 18, 0, tzinfo=UTC),  # Friday evening
    datetime(2026, 10, 23, 23, 59, tzinfo=UTC),  # Friday 23:59
    datetime(2026, 10, 24, 10, 0, tzinfo=UTC),  # Saturday
    datetime(2026, 10, 25, 22, 0, tzinfo=UTC),  # Sunday evening
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
    }
    base.update(kw)
    return ol.evaluate_owner_entry(**base)  # type: ignore[arg-type]


def _codes(reasons: list[str]) -> set[str]:
    return {r.split(":", 1)[0] for r in reasons}


def test_reported_window_is_the_full_utc_day() -> None:
    assert f"{ol.OWNER_SESSION_START_UTC:%H:%M}" == "00:00"
    assert f"{ol.OWNER_SESSION_END_UTC:%H:%M}" == "23:59"


@pytest.mark.parametrize("moment", _FULL_DAY)
def test_session_gate_accepts_the_full_utc_day(moment: datetime) -> None:
    assert ol.in_owner_session(moment) is True
    reasons = _valid(now=moment)
    assert reasons == [], reasons
    assert "OWNER_SESSION" not in _codes(reasons)


def test_naive_and_offset_clocks_use_utc() -> None:
    plus3 = timezone(timedelta(hours=3))
    # Sunday 23:30 UTC is Monday 02:30 at +03:00. Both are eligible.
    assert ol.in_owner_session(datetime(2026, 10, 26, 2, 30, tzinfo=plus3))
    assert ol.in_owner_session(datetime(2026, 10, 26, 10, 0))


@pytest.mark.parametrize("moment", _FULL_DAY)
def test_risk_limits_still_reject_outside_the_former_window(
    moment: datetime,
) -> None:
    assert "OWNER_MAX_SPREAD" in _codes(_valid(now=moment, spread=D("0.46")))
    assert "OWNER_GOLD_ONLY" in _codes(_valid(now=moment, symbol="EURUSD"))
    assert "OWNER_GOLD_ONLY" in _codes(_valid(now=moment, symbol="XAUJPY"))
    assert "OWNER_SL_REQUIRED" in _codes(_valid(now=moment, stop_loss=None))
    low_rr = _valid(now=moment, take_profit=D("3999.00"))
    assert "OWNER_MIN_RR" in _codes(low_rr)
    wide = _valid(
        now=moment,
        stop_loss=D("4010.00"),
        take_profit=D("3970.00"),
        equity=D("50"),
    )
    assert "OWNER_SL_RISK" in _codes(wide)


def test_daily_loss_cap_still_blocks_above_19_percent() -> None:
    assert D("19.0") == ol.OWNER_DAILY_LOSS_PCT
    assert D("9.0") == ol.OWNER_MAX_PLANNED_RISK_PCT
    assert ol.daily_loss_exceeded(daily_pnl=D("-9.51"), base_now=D("40.49")) is True
    assert ol.daily_loss_exceeded(daily_pnl=D("-9.50"), base_now=D("40.50")) is False


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


def test_former_window_does_not_block_auto_resume(
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
    for moment in _FULL_DAY:
        blockers = svc.autonomous_resume_blockers(facts, now=moment)
        assert "outside_session" not in blockers
