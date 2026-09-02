"""Canonical public Signals payload — presentation only, no execution side effects."""

from __future__ import annotations

from typing import Any

import pytest

from app.application.services.jimvio_publisher import build_jimvio_payload
from app.application.services.public_signal_payload import (
    audit_jimvio_payload,
    audit_public_message,
    build_canonical_signal,
    canonical_parity,
    format_public_price,
    public_fields_only,
    render_canonical,
    render_contextual_reply,
    render_lifecycle_update,
    render_public_signal,
    render_status_message,
    render_trade_active,
    validate_canonical_signal,
)
from app.application.services.telegram_events import (
    SIGNAL_CONFIRMED,
    TRADE_OPENED,
    public_channel_notices,
)


def _signal_fields(**extra: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "symbol": "XAUUSD",
        "direction": "SELL",
        "opportunity": 85,
        "confidence": 91,
        "entry": "4610.43357142375",
        "stop_loss": "4376.32357142375",
        "take_profit": "4344.12928572875",
        "risk_reward": "3.0",
        "regime": "STRONG_TREND",
        "ticket": 577877767,
        "volume": "0.01",
        "mt5_ticket": 577877767,
        "deal_id": "d-1",
        "order_id": "o-1",
    }
    fields.update(extra)
    return fields


def _assert_public_clean(text: str) -> None:
    assert audit_public_message(text) == []
    lower = text.lower()
    assert "mt5 ticket" not in lower
    assert "volume:" not in lower
    assert "status: executed" not in lower
    assert "automated trading system" not in lower
    assert "deal_id" not in lower
    assert "order_id" not in lower
    assert "577877767" not in text


@pytest.mark.unit
@pytest.mark.trading_core
class TestCanonicalPublicSignal:
    def test_public_signal_hides_execution_infrastructure(self) -> None:
        text = render_public_signal(_signal_fields())
        _assert_public_clean(text)
        assert "QUANTFORG SIGNAL" in text
        assert "XAUUSD · SELL" in text
        assert "Opportunity" in text
        assert "85" in text
        assert "Confidence" in text
        assert "91%" in text
        assert "Entry" in text
        assert "Stop Loss" in text
        assert "Take Profit" in text
        assert "Risk / Reward" in text
        assert "1 : 3" in text
        assert "Strong Trend" in text
        assert "QuantForg Signals" in text
        assert "4376.32357142375" not in text
        assert "4344.12928572875" not in text

    def test_trade_active_is_separate_from_signal_card(self) -> None:
        signal = render_public_signal(_signal_fields())
        active = render_trade_active(_signal_fields())
        _assert_public_clean(active)
        assert "TRADE ACTIVE" in active
        assert "activated successfully" in active
        assert "QUANTFORG SIGNAL" not in active
        assert signal != active

    def test_symbol_aware_price_precision(self) -> None:
        assert format_public_price("1.08500123", symbol="EURUSD") == "1.085"
        assert format_public_price("173.42591", symbol="USDJPY") == "173.426"
        assert format_public_price("4610.43357142375", symbol="XAUUSD") == "4610.434"
        assert format_public_price("19876.129", symbol="NAS100") == "19876.13"

    def test_internal_fields_stripped_from_public_payload(self) -> None:
        visible = public_fields_only(_signal_fields())
        assert "ticket" not in visible
        assert "mt5_ticket" not in visible
        assert "volume" not in visible
        assert "deal_id" not in visible
        assert visible["symbol"] == "XAUUSD"
        assert visible["opportunity"] == 85

    def test_telegram_and_jimvio_share_canonical_message(self) -> None:
        visible = public_fields_only(_signal_fields())
        payload = build_canonical_signal(
            kind="SIGNAL",
            fields=visible,
            headline="🔴 QUANTFORG SIGNAL",
        )
        telegram = render_canonical(payload)
        jimvio = build_jimvio_payload(
            event=SIGNAL_CONFIRMED,
            event_id="signal:sig-xau",
            message=telegram,
            fields=visible,
        )
        assert jimvio is not None
        assert canonical_parity(telegram, str(jimvio["message"])) == []
        assert audit_jimvio_payload(jimvio) == []
        assert jimvio["status"] == "CONFIRMED"
        assert "mt5_ticket" not in jimvio["metadata"]
        assert jimvio["symbol"] == "XAUUSD"
        assert jimvio["direction"] == "SELL"

    def test_public_channel_rewrite_matches_canonical_cards(self) -> None:
        public = public_channel_notices(
            [
                {
                    "event": TRADE_OPENED,
                    "event_id": "open:577877767",
                    "text": (
                        "internal MT5 Ticket: 577877767 "
                        "Status: EXECUTED Volume: 0.01"
                    ),
                    "fields": _signal_fields(),
                }
            ]
        )
        events = [row["event"] for row in public]
        assert events == [SIGNAL_CONFIRMED, TRADE_OPENED]
        signal, opened = public
        visible = public_fields_only(_signal_fields())
        assert signal["text"] == render_public_signal(visible)
        assert opened["text"] == render_trade_active(visible)
        _assert_public_clean(signal["text"])
        _assert_public_clean(opened["text"])
        assert "ticket" not in signal["fields"]
        assert "volume" not in opened["fields"]

    def test_validate_blocks_incomplete_signal(self) -> None:
        incomplete = {"symbol": "EURUSD", "direction": "BUY"}
        assert "entry" in validate_canonical_signal(incomplete)
        assert validate_canonical_signal(public_fields_only(_signal_fields())) == []

    def test_lifecycle_and_status_copy(self) -> None:
        closed_win = render_lifecycle_update(
            "TAKE_PROFIT",
            public_fields_only(_signal_fields()),
        )
        closed_loss = render_lifecycle_update(
            "STOP_LOSS",
            public_fields_only(_signal_fields()),
        )
        ready = render_status_message("READY")
        scan = render_status_message("SCANNING")
        for text in (closed_win, closed_loss, ready, scan):
            _assert_public_clean(text)
        assert "TRADE COMPLETED" in closed_win
        assert "planned objective" in closed_win
        assert "TRADE COMPLETED" in closed_loss
        assert "Risk remains controlled" in closed_loss
        assert "MARKET WATCH" in ready
        assert "MARKET SCAN" in scan

    def test_replies_follow_lifecycle_without_fabricating(self) -> None:
        active = render_contextual_reply(
            state="ACTIVE", symbol="XAUUSD", direction="SELL"
        )
        closed = render_contextual_reply(state="CLOSED")
        skipped = render_contextual_reply(state="NOT_EXECUTED")
        unknown = render_contextual_reply(state=None)
        for text in (active, closed, skipped, unknown):
            _assert_public_clean(text)
        assert "still active" in active.lower()
        assert "XAUUSD · SELL" in active
        assert "no longer active" in closed.lower()
        assert "was not activated" in skipped.lower()
        assert "unable to confirm" in unknown.lower()

    def test_audit_blocks_legacy_leaks(self) -> None:
        dirty = (
            "QUANTFORG SIGNAL\nMT5 Ticket: 1\nVolume: 0.01\n"
            "Status: EXECUTED ✅\nAutomated Trading System"
        )
        leaks = audit_public_message(dirty)
        assert "MT5 Ticket" in leaks
        assert "Volume:" in leaks
        assert "Status: EXECUTED" in leaks
        assert "Automated Trading System" in leaks
