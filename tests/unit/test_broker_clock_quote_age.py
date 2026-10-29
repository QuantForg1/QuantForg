"""Broker clock versus UTC. The lead is about two hours and is not hardcoded.

A stamp that is still ahead of UTC must not be clamped to age 0. That clamp
treats a quote stale by tens of minutes as fresh whenever the broker clock
leads real UTC by more than the staleness.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.institutional_trading.atr import compute_atr
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    evaluate_market_data_firewall,
)
from app.domain.institutional_trading.quote_clock import (
    quote_age_seconds,
    resolve_quoted_age_for_firewall,
)
from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.market_context.enums import MarketSession
from app.domain.market_universe.data_quality import evaluate_data_quality

_NOW = datetime(2026, 10, 28, 16, 22, tzinfo=UTC)
_OFFSET = timedelta(seconds=7200)


def _clamped_utc_delta(now: datetime, stamp: datetime) -> float:
    """The previous production formula. Kept here only to show the defect."""
    return max(0.0, (now - stamp).total_seconds())


def test_two_hour_lead_hides_thirty_minute_staleness_in_the_old_clamp() -> None:
    fresh = _NOW + _OFFSET
    stale_30m = fresh - timedelta(minutes=30)
    # Both stamps still lead real UTC, so the old clamp reports both as fresh.
    assert _clamped_utc_delta(_NOW, fresh) == 0.0
    assert _clamped_utc_delta(_NOW, stale_30m) == 0.0
    assert fresh > _NOW
    assert stale_30m > _NOW


def test_known_offset_keeps_a_fresh_broker_stamp_fresh() -> None:
    fresh = _NOW + _OFFSET
    age = quote_age_seconds(fresh, now=_NOW, broker_utc_offset=_OFFSET)
    assert age == pytest.approx(0.0)
    # The two-hour lead is not itself the age.
    assert age < 3.0


def test_known_offset_reports_thirty_minute_broker_staleness() -> None:
    stale_30m = _NOW + _OFFSET - timedelta(minutes=30)
    age = quote_age_seconds(stale_30m, now=_NOW, broker_utc_offset=_OFFSET)
    assert age == pytest.approx(1800.0)
    assert age > 120.0


def test_unknown_offset_does_not_treat_a_leading_stamp_as_fresh() -> None:
    fresh = _NOW + _OFFSET
    stale_30m = fresh - timedelta(minutes=30)
    assert quote_age_seconds(fresh, now=_NOW, broker_utc_offset=None) is None
    assert quote_age_seconds(stale_30m, now=_NOW, broker_utc_offset=None) is None


def test_stamp_behind_utc_is_real_age_without_an_offset() -> None:
    stamp = _NOW - timedelta(seconds=45)
    age = quote_age_seconds(stamp, now=_NOW, broker_utc_offset=None)
    assert age == pytest.approx(45.0)


def test_skew_inside_tolerance_is_fresh_and_beyond_tolerance_is_not() -> None:
    almost = _NOW + timedelta(seconds=1)
    ahead = _NOW + timedelta(seconds=10)
    assert quote_age_seconds(almost, now=_NOW) == 0.0
    assert quote_age_seconds(ahead, now=_NOW) is None


def test_firewall_blocks_a_broker_stamp_that_leads_utc() -> None:
    stale_30m = _NOW + _OFFSET - timedelta(minutes=30)
    blocked = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        quote_time=stale_30m,
        now=_NOW,
    )
    assert blocked.allow_new_entry is False
    assert blocked.first_blocking_gate == "QUOTE_CLOCK_UNALIGNED"


def test_firewall_blocks_thirty_minute_staleness_when_offset_is_known() -> None:
    stale_30m = _NOW + _OFFSET - timedelta(minutes=30)
    blocked = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        quote_time=stale_30m,
        now=_NOW,
        broker_utc_offset=_OFFSET,
    )
    assert blocked.allow_new_entry is False
    assert blocked.first_blocking_gate == "STALE_MARKET_DATA"
    assert blocked.quote_age_ms == pytest.approx(1_800_000.0)


def test_firewall_allows_a_fresh_broker_stamp_when_offset_is_known() -> None:
    fresh = _NOW + _OFFSET
    allowed = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        quote_time=fresh,
        now=_NOW,
        broker_utc_offset=_OFFSET,
        max_tick_age_seconds=120.0,
        degraded_tick_age_seconds=60.0,
    )
    assert allowed.allow_new_entry is True
    assert allowed.quote_age_ms == pytest.approx(0.0)


def test_firewall_rejects_an_explicit_negative_age() -> None:
    verdict = evaluate_market_data_firewall(
        symbol="XAUUSD",
        bid=1.0,
        ask=1.1,
        quote_age_seconds=-7200.0,
        now=_NOW,
    )
    assert verdict.allow_new_entry is False
    assert verdict.first_blocking_gate == "QUOTE_CLOCK_UNALIGNED"


def test_legacy_live_context_may_omit_age_but_unaligned_clock_may_not() -> None:
    assert (
        resolve_quoted_age_for_firewall(
            None,
            market_data_live=True,
            quote_clock_unaligned=False,
            has_bid_ask=True,
        )
        == 0.0
    )
    assert (
        resolve_quoted_age_for_firewall(
            0.0,
            market_data_live=True,
            quote_clock_unaligned=True,
            has_bid_ask=True,
        )
        is None
    )


def test_session_classifier_stays_on_utc_and_is_not_shifted_two_hours() -> None:
    utc_1600 = datetime(2026, 10, 28, 16, 0, tzinfo=UTC)
    broker_plus_two = utc_1600 + timedelta(hours=2)
    assert classify_session_utc(utc_1600) is MarketSession.LONDON_NY_OVERLAP
    assert classify_session_utc(broker_plus_two) is MarketSession.NEW_YORK
    weekend = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
    assert classify_session_utc(weekend) is MarketSession.OFF_HOURS


def test_atr_uses_ohlc_only_and_ignores_a_two_hour_label_shift() -> None:
    class _Px:
        def __init__(self, value: str) -> None:
            self.value = Decimal(value)

    class _Bar:
        def __init__(self, high: str, low: str, close: str, label: int) -> None:
            self.high = _Px(high)
            self.low = _Px(low)
            self.close = _Px(close)
            self.open_time_label = label

    def bars(shift: int) -> list[_Bar]:
        out: list[_Bar] = []
        price = Decimal("100")
        for i in range(16):
            price += Decimal("1")
            out.append(_Bar(str(price + 2), str(price - 2), str(price), i + shift))
        return out

    assert compute_atr(bars(0)) == compute_atr(bars(7200))
    assert compute_atr(bars(0)) is not None


def test_data_quality_does_not_call_a_leading_broker_stamp_live() -> None:
    leading = _NOW + _OFFSET
    quality = evaluate_data_quality(
        bid=1.0,
        ask=1.1,
        last_quote_ts=leading,
        now=_NOW,
        history_bars=500,
        market_open=True,
    )
    assert quality.quote_age_seconds is None
    assert quality.state != "LIVE"
    assert quality.quote_freshness != "LIVE"
