"""Gold-only analysis + order-intent boundaries; signal-only notifications."""

from __future__ import annotations

import pytest

from app.application.services.signal_notification_policy import (
    filter_user_signal_notices,
    is_user_signal_event,
    notification_policy_diagnostics,
)
from app.application.services.telegram_events import (
    PUBLIC_MARKET_SCAN,
    PUBLIC_MARKET_WATCH,
    SIGNAL_CONFIRMED,
    SIGNAL_GENERATED,
    public_channel_notices,
)
from app.domain.trading.gold_only import (
    DisabledAutonomousSymbolError,
    map_broker_gold_symbol,
    require_gold_trading_symbol,
)
from app.domain.trading.gold_unified_brain import decide_gold

pytestmark = [pytest.mark.unit]


def test_require_gold_rejects_fx_crypto_indices() -> None:
    for symbol in ("EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "NAS100", "US30"):
        with pytest.raises(DisabledAutonomousSymbolError):
            require_gold_trading_symbol(symbol)


def test_require_gold_accepts_broker_suffixes() -> None:
    assert require_gold_trading_symbol("XAUUSD_i").upper().startswith("XAU")
    assert require_gold_trading_symbol("XAUUSD.a").upper().startswith("XAU")
    assert map_broker_gold_symbol("GOLD") is not None
    assert map_broker_gold_symbol("EURUSD") is None


def test_unified_brain_rejects_non_gold_at_analysis() -> None:
    d = decide_gold(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "quote_age_seconds": 1,
            "reject": False,
        }
    )
    assert d.decision == "NO_TRADE"
    assert "Non-Gold" in d.reasons[0]


def test_order_intent_rejects_non_gold() -> None:
    from app.application.services.institutional_execution_engine import (
        parse_order_intent,
    )
    from app.domain.exceptions.base import ValidationError

    with pytest.raises(ValidationError) as exc:
        parse_order_intent(
            symbol="EURUSD",
            side="buy",
            order_type="market",
            volume="0.01",
        )
    assert str(exc.value.code) == "DISABLED_AUTONOMOUS_SYMBOL"


def test_scanner_chatter_events_blocked_for_users() -> None:
    assert is_user_signal_event(PUBLIC_MARKET_SCAN) is False
    assert is_user_signal_event(PUBLIC_MARKET_WATCH) is False
    assert is_user_signal_event(SIGNAL_GENERATED) is True
    assert is_user_signal_event(SIGNAL_CONFIRMED) is True
    filtered = filter_user_signal_notices(
        [
            {"event": PUBLIC_MARKET_SCAN, "event_id": "scan", "text": "scan"},
            {
                "event": SIGNAL_CONFIRMED,
                "event_id": "sig",
                "text": "ok",
                "fields": {"symbol": "XAUUSD"},
            },
            {
                "event": SIGNAL_CONFIRMED,
                "event_id": "fx",
                "text": "bad",
                "fields": {"symbol": "EURUSD"},
            },
        ]
    )
    assert len(filtered) == 1
    assert filtered[0]["event_id"] == "sig"
    diag = notification_policy_diagnostics()
    assert diag["scanner_chatter_disabled"] is True
    assert diag["gold_only_user_channel"] is True


def test_public_channel_drops_non_gold_confirmed() -> None:
    notices = [
        {
            "event": SIGNAL_CONFIRMED,
            "event_id": "sigconf:eur",
            "text": "x",
            "fields": {
                "symbol": "EURUSD",
                "direction": "BUY",
                "entry": "1.1",
                "stop_loss": "1.09",
                "take_profit": "1.12",
                "opportunity": "88",
            },
        }
    ]
    assert public_channel_notices(notices) == []
