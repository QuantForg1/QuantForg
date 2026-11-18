"""signal_history keeps the intended side and quote of rejected signals."""

from __future__ import annotations

from typing import Any

import pytest

from app.application.services import signal_intelligence_service as svc

pytestmark = pytest.mark.unit


def _rejected_sell() -> dict[str, Any]:
    return {
        "symbol": "XAUUSD",
        "direction": "SELL",
        "reject": True,
        "reject_reason": "OWNER_MIN_RR: net reward:risk 0.86 < 1.50",
        "bid": "3768.073",
        "ask": "3768.427",
        "spread": "0.354",
        "gate_atr": "6.57357143",
        "stop_atr": "2.98071429",
        "bearish_score": 68,
        "bullish_score": 24,
        "ltf_buy_score": 16,
        "ltf_sell_score": 36,
        "sniper_entry": {
            "zone_bound": "3772.303",
            "primary_reason": "WAIT_INSUFFICIENT_RR",
        },
    }


def test_shadow_keeps_side_quote_and_stop_volatility() -> None:
    out = svc.shadow_intent(_rejected_sell())
    assert out["intended_direction"] == "SELL"
    assert out["intended_source"] == "direction"
    assert out["bid"] == pytest.approx(3768.073)
    assert out["ask"] == pytest.approx(3768.427)
    assert out["stop_atr"] == pytest.approx(2.98071429)
    assert out["sell_score"] == 68.0
    assert out["buy_score"] == 24.0
    assert out["zone_bound"] == pytest.approx(3772.303)
    assert out["sniper_reason"] == "WAIT_INSUFFICIENT_RR"


def test_side_falls_back_to_sniper_then_scores() -> None:
    row = _rejected_sell() | {"direction": "WAIT", "sniper_entry": {"action": "buy"}}
    assert svc.shadow_intent(row)["intended_source"] == "sniper_action"
    row = _rejected_sell() | {"direction": "WAIT", "sniper_entry": {}}
    out = svc.shadow_intent(row)
    assert (out["intended_direction"], out["intended_source"]) == ("SELL", "ltf_scores")
    tie = {"direction": "WAIT", "ltf_buy_score": 16, "ltf_sell_score": 16}
    assert "intended_direction" not in svc.shadow_intent(tie)


def test_history_row_carries_shadow_without_changing_projection() -> None:
    row = svc._score_to_history_row(_rejected_sell(), scan_as_of="2026-11-18T14:40:21Z")
    assert row["raw_score"]["shadow"]["intended_direction"] == "SELL"
    assert row["reject"] is True
    assert row["source"] == "live_multi_asset_scan"


def test_bad_values_are_skipped_not_raised() -> None:
    out = svc.shadow_intent({"bid": "n/a", "ask": True, "stop_atr": None})
    assert out == {}
    assert svc._shadow_block({"bid": "x"}) == {}
