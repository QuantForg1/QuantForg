"""SELL cascade protection recovers after a transient broker read failure.

Regression for 18 Nov 2026: Railway restarted while the MT5 gateway was down,
startup recovery marked SELL protection untrusted (positions_unavailable) and
nothing retried, so every SELL was blocked until the next deploy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.domain.institutional_trading.ai_scalping import (
    sell_cascade_anchor_store as store,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


@pytest.fixture(autouse=True)
def _clean() -> Any:
    store.reset_sell_cascade_store_for_tests()
    yield
    store.reset_sell_cascade_store_for_tests()


def _inline(fn: Callable[[], None]) -> None:
    fn()


def test_transient_failure_is_retried_and_restores_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    def _recover(adapter: Any) -> dict[str, Any]:
        calls.append(adapter)
        with store._LOCK:
            store._TRUSTED = True
            store._UNTRUSTED_REASON = None
        return {"trusted": True}

    monkeypatch.setattr(store, "recover_sell_cascade_on_startup", _recover)
    store._mark_untrusted("positions_unavailable")
    adapter = object()
    assert store.maybe_retry_sell_cascade_recovery(adapter, now_mono=0, spawn=_inline)
    assert calls == [adapter]
    assert store._TRUSTED is True
    # Trusted again: further cycles do nothing.
    assert not store.maybe_retry_sell_cascade_recovery(
        adapter, now_mono=1000, spawn=_inline
    )


def test_retry_is_throttled_and_single_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    pending: list[Callable[[], None]] = []
    monkeypatch.setattr(
        store,
        "recover_sell_cascade_on_startup",
        lambda _adapter: calls.append(1) or {"trusted": False},
    )
    store._mark_untrusted("broker_history_unavailable")
    adapter = object()
    assert store.maybe_retry_sell_cascade_recovery(
        adapter, now_mono=0, spawn=pending.append
    )
    # Still running in the background: no second retry.
    assert not store.maybe_retry_sell_cascade_recovery(
        adapter, now_mono=500, spawn=pending.append
    )
    pending.pop()()
    assert calls == [1]
    # Finished but inside the interval: wait.
    assert not store.maybe_retry_sell_cascade_recovery(
        adapter, now_mono=60, spawn=_inline
    )
    assert store.maybe_retry_sell_cascade_recovery(
        adapter, now_mono=store.RETRY_MIN_INTERVAL_SECONDS + 1, spawn=_inline
    )
    assert calls == [1, 1]


def test_sell_stays_blocked_until_retry_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        store, "recover_sell_cascade_on_startup", lambda _adapter: {"trusted": False}
    )
    store._mark_untrusted("positions_unavailable")
    monkeypatch.setattr(store, "active_anchors", lambda _symbol: ([], store._TRUSTED))
    store.maybe_retry_sell_cascade_recovery(object(), now_mono=0, spawn=_inline)
    blocked, why = store.evaluate_durable_sell_cascade(
        symbol="XAUUSD", direction="SELL", entry_price="3768", reversal_confirmed=False
    )
    assert blocked is True
    assert why == store.PROTECTION_UNAVAILABLE


def test_non_transient_or_forced_down_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        store,
        "recover_sell_cascade_on_startup",
        lambda _adapter: pytest.fail("must not retry"),
    )
    store._mark_untrusted("reconcile_conflict")
    assert not store.maybe_retry_sell_cascade_recovery(
        object(), now_mono=0, spawn=_inline
    )
    store.reset_sell_cascade_store_for_tests()
    store.force_sell_cascade_store_unavailable_for_tests(True)
    with store._LOCK:
        store._UNTRUSTED_REASON = "positions_unavailable"
    assert not store.maybe_retry_sell_cascade_recovery(
        object(), now_mono=0, spawn=_inline
    )
    assert not store.maybe_retry_sell_cascade_recovery(None, now_mono=0, spawn=_inline)
