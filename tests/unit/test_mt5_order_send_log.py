"""Unit tests for MT5 order_send operator audit logs."""

from __future__ import annotations

from app.infrastructure.brokers.mt5.order_send_log import (
    format_mt5_order_send_request,
    format_mt5_order_send_response,
    log_mt5_order_send_exchange,
)


def test_format_request_includes_required_fields() -> None:
    text = format_mt5_order_send_request(
        symbol="EURUSD",
        side="sell",
        volume="0.01",
        price="1.13700",
        stop_loss="1.14000",
        take_profit="1.13100",
    )
    assert text.startswith("MT5 order_send()")
    assert "- symbol: EURUSD" in text
    assert "- side: SELL" in text
    assert "- volume: 0.01" in text
    assert "- price: 1.13700" in text
    assert "- SL: 1.14000" in text
    assert "- TP: 1.13100" in text


def test_format_response_includes_retcode_and_tickets() -> None:
    text = format_mt5_order_send_response(
        retcode=10016,
        comment="Invalid stops",
        deal=0,
        order=0,
        ticket=0,
    )
    assert "- retcode: 10016" in text
    assert "- comment: Invalid stops" in text
    assert "- deal: 0" in text
    assert "- order: 0" in text
    assert "- ticket: 0" in text


def test_log_exchange_accepted(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class _FakeLog:
        def warning(self, msg: object, *args: object, **kwargs: object) -> None:
            calls.append(("warning", str(msg)))

        def error(self, msg: object, *args: object, **kwargs: object) -> None:
            calls.append(("error", str(msg)))

    monkeypatch.setattr(
        "app.infrastructure.brokers.mt5.order_send_log.logger",
        _FakeLog(),
    )
    log_mt5_order_send_exchange(
        symbol="EURUSD",
        side="buy",
        volume="0.01",
        price="1.13",
        stop_loss="1.12",
        take_profit="1.15",
        retcode=10009,
        comment="Request executed",
        deal=9001,
        order=8001,
        ticket=8001,
    )
    joined = "\n".join(msg for _, msg in calls)
    assert "MT5 order_send()" in joined
    assert "ORDER ACCEPTED" in joined
    assert "Position Opened" in joined
    assert "retcode: 10009" in joined
    assert any(level == "warning" and "ORDER ACCEPTED" in msg for level, msg in calls)


def test_log_exchange_rejected(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class _FakeLog:
        def warning(self, msg: object, *args: object, **kwargs: object) -> None:
            calls.append(("warning", str(msg)))

        def error(self, msg: object, *args: object, **kwargs: object) -> None:
            calls.append(("error", str(msg)))

    monkeypatch.setattr(
        "app.infrastructure.brokers.mt5.order_send_log.logger",
        _FakeLog(),
    )
    log_mt5_order_send_exchange(
        symbol="EURUSD",
        side="sell",
        volume="0.01",
        price="1.13",
        stop_loss="1.14",
        take_profit="1.11",
        retcode=10016,
        comment="Invalid stops",
        deal=0,
        order=0,
        ticket=0,
    )
    joined = "\n".join(msg for _, msg in calls)
    assert "ORDER REJECTED" in joined
    assert "retcode: 10016" in joined
    assert "Invalid stops" in joined
    assert any(level == "error" and "ORDER REJECTED" in msg for level, msg in calls)
