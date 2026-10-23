"""Final owner check on the exact tick the market request is built from.

Owner review 2026-10-23: trades 1 and 4 passed the owner guard on a tick a
few hundred ms older than the one the order was sent at; at the send tick
their RR after spread was already below 1.50. The pre-send check re-reads the
tick, builds the request from it and re-runs the full owner check on that
same price before ``order_send``.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D
from uuid import uuid4

import pytest

from app.application.services import institutional_execution_engine as iee
from app.domain.institutional_trading import owner_live_limits as ol

pytestmark = pytest.mark.unit


def _sell(
    price: str,
    sl: str,
    tp: str,
    spread: str,
    *,
    plan: str | None = None,
    buffer: str = "0",
) -> list[str]:
    bid = D(price)
    return ol.presend_owner_violations(
        symbol="XAUUSD",
        side="SELL",
        volume=D("0.01"),
        request_price=bid,
        bid=bid,
        ask=bid + D(spread),
        stop_loss=D(sl),
        take_profit=D(tp),
        plan_price=D(plan) if plan else None,
        contract_size=D("100"),
        equity=D("55"),
        rr_buffer=D(buffer),
    )


def test_slippage_buffer_defaults_to_zero() -> None:
    assert ol.OWNER_RR_SLIPPAGE_BUFFER.is_zero()


def test_trade_4_at_the_send_tick_is_refused() -> None:
    # 5.220 / (3.168 + 0.424) = 1.453 < 1.50
    reasons = _sell("4018.033", "4021.201", "4012.813", "0.424")
    assert any(r.startswith("PRESEND OWNER_MIN_RR") for r in reasons), reasons


def test_trade_1_is_refused_by_rr_not_by_the_drift_guard() -> None:
    # Plan 4019.155 -> stop 2.715; send tick 4018.853 -> 3.017 (wider, no
    # drift). RR 5.140 / (3.017 + 0.424) = 1.494 < 1.50.
    reasons = _sell("4018.853", "4021.870", "4013.713", "0.424", plan="4019.155")
    assert any("OWNER_MIN_RR" in r for r in reasons), reasons
    assert not any("OWNER_PRICE_DRIFT" in r for r in reasons)


def test_trade_2_passes() -> None:
    # 6.100 / (3.057 + 0.344) = 1.794
    assert _sell("4019.813", "4022.870", "4013.713", "0.344") == []


def test_buffer_is_applied_to_rr_when_set() -> None:
    # Trade 2 with B = 0.45: 5.650 / (3.057 + 0.344 + 0.45) = 1.467 < 1.50.
    reasons = _sell("4019.813", "4022.870", "4013.713", "0.344", buffer="0.45")
    assert reasons and reasons[0].startswith("PRESEND OWNER_MIN_RR_SLIPPAGE")
    assert _sell("4019.813", "4022.870", "4013.713", "0.344", buffer="0.25") == []


def test_spread_comes_from_the_same_tick() -> None:
    # Same price, spread above the 0.45 cap at the send tick.
    reasons = _sell("4019.813", "4022.870", "4013.713", "0.50")
    assert any("OWNER_MAX_SPREAD" in r for r in reasons), reasons


def _run(monkeypatch: pytest.MonkeyPatch, *, move: str):
    """BUY 0.01 at mock ask 2320.80, SL 2319.00, TP 2324.00, spread 0.30.

    RR at the owner-guard tick: 3.20 / (1.80 + 0.30) = 1.52. After the owner
    guard has run, the tick moves by ``move``.
    """
    from tests.unit.test_manual_ticket_owner_limits import _engine

    engine, client = _engine()
    original_tick = client.latest_tick
    original_guard = iee.evaluate_owner_entry
    guard_ran = {"done": False}

    def guard(**kwargs):
        out = original_guard(**kwargs)
        guard_ran["done"] = True
        return out

    def tick(symbol: str):
        t = original_tick(symbol)
        if not guard_ran["done"]:
            return t
        return replace(t, bid=t.bid + D(move), ask=t.ask + D(move))

    sent: list = []
    original_send = client.order_send

    def order_send(request):
        sent.append(request)
        return original_send(request)

    monkeypatch.setattr(iee, "evaluate_owner_entry", guard)
    monkeypatch.setattr(client, "latest_tick", tick)
    monkeypatch.setattr(client, "order_send", order_send)
    intent = iee.parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.00",
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id=f"presend-{move}",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert guard_ran["done"], pipeline
    return pipeline, sent, client


def test_run_submit_refuses_when_rr_fails_at_the_send_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ask 2320.90 at the send tick: 3.10 / (1.90 + 0.30) = 1.41.
    pipeline, sent, client = _run(monkeypatch, move="0.10")
    assert pipeline.outcome == "rejected"
    assert "PRESEND OWNER_MIN_RR" in pipeline.message
    assert sent == []
    assert client._positions == []
    meta = next(
        s.meta
        for s in pipeline.stages
        if (s.meta or {}).get("component") == "owner_presend_check"
    )
    assert meta["check_price"] == "2320.90"
    assert meta["check_spread"] == "0.30"


def test_run_submit_sends_the_exact_checked_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ask 2320.70 at the send tick: 3.30 / (1.70 + 0.30) = 1.65 -> sent at it.
    pipeline, sent, _client = _run(monkeypatch, move="-0.10")
    assert "PRESEND" not in pipeline.message
    assert len(sent) == 1
    assert sent[0].price == D("2320.70")


def test_run_submit_fails_closed_when_the_presend_check_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(**_kwargs):
        raise RuntimeError("tick unavailable")

    monkeypatch.setattr(iee, "presend_owner_violations", broken)
    pipeline, sent, _client = _run(monkeypatch, move="0")
    assert pipeline.outcome == "rejected"
    assert "PRESEND owner check unavailable, fail-closed" in pipeline.message
    assert sent == []
