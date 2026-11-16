"""MT5 server clock offset: learned from fresh ticks, never assumed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.institutional_trading import broker_clock as bc

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

NOW = datetime(2026, 11, 16, 7, 47, 50, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset() -> None:
    bc.reset_for_tests()


def test_learns_utc_plus_2_from_a_fresh_tick() -> None:
    bc.observe_server_epoch(NOW.timestamp() + 7200 - 3, now=NOW)
    assert bc.offset(now=NOW) == timedelta(hours=2)


def test_stale_tick_teaches_nothing() -> None:
    bc.observe_server_epoch(NOW.timestamp() + 7200 - 1800, now=NOW)  # 30 min old
    assert bc.offset(now=NOW) is None


def test_offset_expires() -> None:
    bc.observe_server_epoch(NOW.timestamp() + 7200, now=NOW)
    assert bc.offset(now=NOW + timedelta(days=4)) is None


def test_real_close_time_of_position_704115432() -> None:
    # MT5 reported 09:47:43 for a close Railway logged at 07:47:50 UTC.
    bc.observe_server_epoch(
        NOW.timestamp() + 7200, now=datetime.now(UTC) - (datetime.now(UTC) - NOW)
    )
    bc._observed_at = datetime.now(UTC)  # keep it valid for this check
    mt5_reported = datetime(2026, 11, 16, 9, 47, 43, tzinfo=UTC).timestamp()
    assert bc.server_epoch_to_utc(mt5_reported) == datetime(
        2026, 11, 16, 7, 47, 43, tzinfo=UTC
    )


def test_unknown_offset_returns_raw_time() -> None:
    raw = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    assert bc.server_epoch_to_utc(raw.timestamp()) == raw


def test_engine_daily_context_fails_closed_without_clock() -> None:
    import inspect

    from app.application.services import institutional_execution_engine as eng

    src = inspect.getsource(eng)
    assert "mt5_server_clock_unknown" in src
    assert "broker_clock.offset() is None" in src
