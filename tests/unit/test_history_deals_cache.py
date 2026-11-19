"""Today's deals are fetched fresh; older history is cached between cycles."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.application.services import ite_cycle_market_context as ctx


class _Adapter:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []
        self.fail_older = False
        self.fail_today = False

    def history_deals(self, *, date_from: datetime, date_to: datetime) -> list[Any]:
        self.calls.append((date_from, date_to))
        day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        if date_from >= day:
            if self.fail_today:
                raise RuntimeError("timeout")
            return [SimpleNamespace(ticket=2, time=day + timedelta(hours=1))]
        if self.fail_older:
            raise RuntimeError("timeout")
        return [SimpleNamespace(ticket=1, time=day - timedelta(days=3))]


@pytest.fixture(autouse=True)
def _clear() -> None:
    ctx._HISTORY_CACHE.clear()


def _window() -> tuple[datetime, datetime]:
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=10), datetime.now(UTC) + timedelta(days=1)


def test_older_history_is_reused_today_is_fresh() -> None:
    adapter = _Adapter()
    start, end = _window()
    clock = [1000.0]
    ok, deals, _ = ctx._load_history_deals(
        adapter, date_from=start, date_to=end, now=lambda: clock[0]
    )
    assert ok and [d.ticket for d in deals or []] == [1, 2]
    assert len(adapter.calls) == 2
    clock[0] += 60
    ok, deals, _ = ctx._load_history_deals(
        adapter, date_from=start, date_to=end, now=lambda: clock[0]
    )
    assert ok and [d.ticket for d in deals or []] == [1, 2]
    assert len(adapter.calls) == 3  # only today's window again


def test_today_failure_is_never_trusted() -> None:
    adapter = _Adapter()
    start, end = _window()
    adapter.fail_today = True
    with pytest.raises(RuntimeError):
        ctx._load_history_deals(adapter, date_from=start, date_to=end)


def test_stale_older_copy_used_when_refresh_fails() -> None:
    adapter = _Adapter()
    start, end = _window()
    clock = [0.0]
    assert ctx._load_history_deals(
        adapter, date_from=start, date_to=end, now=lambda: clock[0]
    )[0]
    adapter.fail_older = True
    clock[0] += 600  # past refresh, inside 1 h
    ok, deals, _ = ctx._load_history_deals(
        adapter, date_from=start, date_to=end, now=lambda: clock[0]
    )
    assert ok and [d.ticket for d in deals or []] == [1, 2]
    clock[0] += 4000  # past max stale
    ok, deals, note = ctx._load_history_deals(
        adapter, date_from=start, date_to=end, now=lambda: clock[0]
    )
    assert ok is False and deals is None and note
