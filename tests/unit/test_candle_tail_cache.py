"""Incremental candle fetch: tail merge is exact, gaps force a full refetch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.services.candle_tail_cache import RatesTailCache

T0 = datetime(2026, 11, 19, tzinfo=UTC)


@dataclass(frozen=True)
class R:
    open_time: datetime
    close: float


def bars(start: int, n: int, *, bump: float = 0.0) -> list[R]:
    return [
        R(T0 + timedelta(minutes=i), float(i) + bump) for i in range(start, start + n)
    ]


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_first_call_is_full_then_tail():
    c = RatesTailCache(tail=5, full_refresh_seconds=300, clock=Clock())
    key = ("a", "XAUUSD", "M1")
    assert c.plan(key, 100) == 100
    assert c.merge(key, 100, bars(0, 100), full=True) == bars(0, 100)
    assert c.plan(key, 100) == 5


def test_tail_merge_updates_forming_bar_and_appends_new_bar():
    c = RatesTailCache(tail=5, clock=Clock())
    key = ("a", "XAUUSD", "M1")
    c.merge(key, 100, bars(0, 100), full=True)
    # broker returns last 5 bars: 96..99 with a revised forming bar 99 + new bar 100
    tail = [
        *bars(96, 3),
        R(T0 + timedelta(minutes=99), 999.0),
        R(T0 + timedelta(minutes=100), 100.0),
    ]
    merged = c.merge(key, 100, tail, full=False)
    assert merged is not None
    assert len(merged) == 100
    assert merged[0].open_time == T0 + timedelta(minutes=1)  # window slid by one
    assert merged[-2].close == 999.0  # forming bar replaced, not duplicated
    assert merged[-1].open_time == T0 + timedelta(minutes=100)
    times = [r.open_time for r in merged]
    assert times == sorted(set(times))  # strictly increasing, no duplicates


def test_merged_series_equals_a_fresh_full_fetch():
    c = RatesTailCache(tail=5, clock=Clock())
    key = ("a", "XAUUSD", "M5")
    c.merge(key, 50, bars(0, 50), full=True)
    for step in range(1, 4):
        merged = c.merge(key, 50, bars(50 + step - 5, 5), full=False)
        assert merged == bars(step, 50)


def test_gap_forces_full_refetch():
    c = RatesTailCache(tail=5, clock=Clock())
    key = ("a", "XAUUSD", "M1")
    c.merge(key, 100, bars(0, 100), full=True)
    # gateway was down for 20 minutes: tail starts after the cached end
    assert c.merge(key, 100, bars(120, 5), full=False) is None


def test_empty_or_stale_tail_is_rejected():
    c = RatesTailCache(tail=5, clock=Clock())
    key = ("a", "XAUUSD", "M1")
    c.merge(key, 100, bars(0, 100), full=True)
    assert c.merge(key, 100, [], full=False) is None
    assert c.merge(key, 100, bars(10, 5), full=False) is None


def test_periodic_full_refresh_and_larger_count():
    clock = Clock()
    c = RatesTailCache(tail=5, full_refresh_seconds=300, clock=clock)
    key = ("a", "XAUUSD", "H1")
    c.merge(key, 100, bars(0, 100), full=True)
    assert c.plan(key, 200) == 200  # needs more history than cached
    clock.t = 299
    assert c.plan(key, 100) == 5
    clock.t = 300
    assert c.plan(key, 100) == 100


def test_keys_are_isolated_per_adapter_symbol_timeframe():
    c = RatesTailCache(tail=5, clock=Clock())
    c.merge(("a", "XAUUSD", "M1"), 10, bars(0, 10), full=True)
    assert c.plan(("b", "XAUUSD", "M1"), 10) == 10
    assert c.plan(("a", "XAUUSD", "M5"), 10) == 10
