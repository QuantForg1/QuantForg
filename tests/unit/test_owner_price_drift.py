"""Market entries must not go out with a stop that shrank since the signal.

Production 2026-10-23 07:31Z: SELL signal at 4019.155 with SL 4021.870 (stop
2.715 = 1.5 x M1 ATR). The order was sent 10 s later and filled at 4020.323,
so the real stop was 1.547 (43% narrower) and was hit 41 s later. The pre-send
checks used the signal price instead of the live bid.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _check(side: str, signal: str, live: str, sl: str) -> str | None:
    return ol.stop_shrink_violation(
        side=side, signal_price=D(signal), live_price=D(live), stop_loss=D(sl)
    )


def test_production_case_is_refused() -> None:
    reason = _check("SELL", "4019.155", "4020.323", "4021.870")
    assert reason is not None
    assert reason.startswith("OWNER_PRICE_DRIFT")
    assert "2.72 to 1.55" in reason


def test_ten_percent_boundary_sell() -> None:
    # planned 2.00; 10% shrink allowed -> live distance 1.80 ok, 1.79 refused
    assert _check("SELL", "100.00", "100.20", "102.00") is None
    assert _check("SELL", "100.00", "100.21", "102.00") is not None


def test_ten_percent_boundary_buy() -> None:
    assert _check("BUY", "100.00", "99.80", "98.00") is None
    assert _check("BUY", "100.00", "99.79", "98.00") is not None


def test_price_beyond_stop_is_refused() -> None:
    assert "beyond the stop loss" in (
        _check("SELL", "100.00", "102.10", "102.00") or ""
    )
    assert "beyond the stop loss" in (_check("BUY", "100.00", "97.90", "98.00") or "")


def test_favourable_drift_is_not_this_guards_concern() -> None:
    # Stop got wider: the 9% planned-risk and RR guards judge that case.
    assert _check("SELL", "100.00", "99.00", "102.00") is None
    assert _check("BUY", "100.00", "101.00", "98.00") is None


@pytest.mark.parametrize(
    ("signal", "live", "sl"),
    [
        (None, "100", "102"),
        ("100", None, "102"),
        ("100", "100", None),
        ("0", "100", "102"),
    ],
)
def test_unknown_inputs_defer_to_other_guards(
    signal: str | None, live: str | None, sl: str | None
) -> None:
    assert (
        ol.stop_shrink_violation(
            side="SELL",
            signal_price=D(signal) if signal else None,
            live_price=D(live) if live else None,
            stop_loss=D(sl) if sl else None,
        )
        is None
    )
