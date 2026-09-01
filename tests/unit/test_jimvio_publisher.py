"""Jimvio webhook publisher — HMAC, fail-open, never on the trading path."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.application.services.jimvio_publisher import (
    DEFAULT_JIMVIO_WEBHOOK_URL,
    SIGNATURE_HEADER,
    JimvioPublisher,
    build_jimvio_payload,
    build_test_payload,
    emit_jimvio,
    jimvio_signature,
    map_jimvio_event_type,
    reset_jimvio_publisher_for_tests,
    serialize_jimvio_body,
    signed_request,
)
from app.application.services.telegram_dispatcher import (
    TelegramDispatcher,
    emit_telegram,
    notify_cycle,
    reset_telegram_dispatcher_for_tests,
)
from app.application.services.telegram_events import (
    SIGNAL_GENERATED,
    TRADE_OPENED,
)
from core.config.settings import AppEnvironment, Settings

SECRET = "jimvio-test-secret-do-not-log"


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.headers: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _reset_publishers() -> None:
    reset_jimvio_publisher_for_tests(None)
    reset_telegram_dispatcher_for_tests(None)
    yield
    reset_jimvio_publisher_for_tests(None)
    reset_telegram_dispatcher_for_tests(None)


def _publisher(
    sender: Any,
    *,
    enabled: bool = True,
    secret: str | None = SECRET,
) -> JimvioPublisher:
    pub = JimvioPublisher(
        enabled=enabled,
        webhook_url=DEFAULT_JIMVIO_WEBHOOK_URL,
        secret=SecretStr(secret) if secret else None,
        sender=sender,
        timeout_seconds=0.2,
        max_attempts=3,
    )
    reset_jimvio_publisher_for_tests(pub)
    return pub


@pytest.mark.unit
class TestJimvioHmac:
    def test_signature_is_hmac_sha256_hex_of_raw_body(self) -> None:
        body = b'{"event_id":"abc","event_type":"SIGNAL"}'
        digest = jimvio_signature(body, SECRET)
        expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert digest == expected
        assert len(digest) == 64

    def test_signed_request_matches_serialized_body(self) -> None:
        payload = {"event_id": "x", "event_type": "SYSTEM_ERROR", "status": "TEST"}
        body, signature = signed_request(payload, SECRET)
        assert body == serialize_jimvio_body(payload)
        assert signature == jimvio_signature(body, SECRET)
        pretty = serialize_jimvio_body(payload).replace(b":", b": ")
        assert pretty != body
        assert jimvio_signature(pretty, SECRET) != signature

    def test_missing_secret_refuses_to_sign(self) -> None:
        with pytest.raises(ValueError, match="missing_webhook_secret"):
            jimvio_signature(b"{}", "")

    def test_secret_not_in_exception_or_payload(self) -> None:
        payload = build_test_payload()
        dumped = str(payload)
        assert SECRET not in dumped
        try:
            jimvio_signature(b"{}", "")
        except ValueError as exc:
            assert SECRET not in str(exc)


@pytest.mark.unit
class TestJimvioPayload:
    def test_signal_generated_maps_to_detected(self) -> None:
        assert map_jimvio_event_type(SIGNAL_GENERATED) == "SIGNAL_DETECTED"
        payload = build_jimvio_payload(
            event=SIGNAL_GENERATED,
            event_id="sig:EURUSD|BUY|1.1|1.0|1.2",
            message="signal",
            fields={
                "symbol": "EURUSD",
                "direction": "BUY",
                "entry": "1.17012",
                "stop_loss": "1.16500",
                "take_profit": "1.18000",
            },
            timestamp="2026-09-01T00:00:00Z",
        )
        assert payload is not None
        assert payload["event_type"] == "SIGNAL_DETECTED"
        assert payload["event_id"] == "sig:EURUSD|BUY|1.1|1.0|1.2"
        assert payload["symbol"] == "EURUSD"
        assert payload["direction"] == "BUY"
        assert payload["entry"] == pytest.approx(1.17012)
        assert payload["status"] == "DETECTED"
        assert payload["metadata"]["quantforg_event"] == SIGNAL_GENERATED

    def test_trade_opened_executed_requires_ticket(self) -> None:
        opened = build_jimvio_payload(
            event=TRADE_OPENED,
            event_id="open:575000111",
            fields={"symbol": "USDJPY", "direction": "BUY", "ticket": 575000111},
        )
        assert opened is not None
        assert opened["status"] == "EXECUTED"
        assert opened["metadata"]["mt5_ticket"] == 575000111
        ghost = build_jimvio_payload(
            event=TRADE_OPENED,
            event_id="open:missing",
            fields={"symbol": "USDJPY", "direction": "BUY"},
        )
        assert ghost is not None
        assert ghost["event_type"] == "TRADE_REJECTED"
        assert ghost["status"] == "REJECTED"

    def test_telegram_test_is_not_published(self) -> None:
        assert map_jimvio_event_type("TELEGRAM_TEST") is None
        assert (
            build_jimvio_payload(
                event="TELEGRAM_TEST", event_id="telegram:test", message="x"
            )
            is None
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestJimvioDelivery:
    async def test_valid_request_signs_raw_body(self) -> None:
        captured: dict[str, Any] = {}

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return _FakeResponse(200, '{"ok":true}')

        pub = _publisher(sender)
        pub.emit(
            SIGNAL_GENERATED,
            "sig:1",
            "hello",
            fields={"symbol": "XAUUSD", "direction": "BUY", "entry": 3480.2},
        )
        await pub.flush()
        assert captured["url"] == DEFAULT_JIMVIO_WEBHOOK_URL
        assert captured["headers"]["Content-Type"] == "application/json"
        digest = captured["headers"][SIGNATURE_HEADER]
        assert digest == jimvio_signature(captured["body"], SECRET)
        assert SECRET not in captured["body"].decode()
        assert pub.last_success is True

    async def test_timeout_retries_then_fails_open(self) -> None:
        hits = {"n": 0}

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            hits["n"] += 1
            raise httpx.TimeoutException("timed out")

        pub = _publisher(sender)
        pub.emit("SYSTEM_ERROR", "sys:timeout", "err")
        await pub.flush(wait_seconds=8)
        assert hits["n"] == 3
        assert pub.last_success is False

    async def test_retry_keeps_stable_event_id(self) -> None:
        ids: list[str] = []

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            ids.append(body.decode())
            return _FakeResponse(500, "oops")

        pub = _publisher(sender)
        pub.emit("SYSTEM_ERROR", "sys:stable", "err")
        await pub.flush(wait_seconds=8)
        assert len(ids) == 3
        assert len(set(ids)) == 1
        assert '"event_id":"sys:stable"' in ids[0]


@pytest.mark.unit
class TestJimvioQueue:
    def test_duplicate_event_id_is_not_requeued(self) -> None:
        called = {"n": 0}

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            called["n"] += 1
            return _FakeResponse(200)

        pub = _publisher(sender)
        pub.emit("SYSTEM_ERROR", "sys:dup", "one")
        pub.emit("SYSTEM_ERROR", "sys:dup", "two")
        assert pub.pending == 1

    def test_missing_secret_disables_publisher(self) -> None:
        pub = JimvioPublisher(
            enabled=True,
            webhook_url=DEFAULT_JIMVIO_WEBHOOK_URL,
            secret=None,
        )
        assert pub.enabled is False
        pub.emit("SYSTEM_ERROR", "sys:1", "x")
        assert pub.pending == 0

    def test_disabled_is_noop(self) -> None:
        called = {"n": 0}

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            called["n"] += 1
            return _FakeResponse(200)

        pub = _publisher(sender, enabled=False)
        pub.emit_test()
        assert pub.pending == 0
        assert called["n"] == 0


@pytest.mark.unit
@pytest.mark.trading_core
class TestJimvioDoesNotAffectTelegram:
    def test_jimvio_failure_still_enqueues_telegram(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_a: Any, **_k: Any) -> None:
            raise RuntimeError("jimvio down")

        monkeypatch.setattr(
            "app.application.services.jimvio_publisher.emit_jimvio",
            boom,
        )

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            return _FakeResponse(200)

        disp = TelegramDispatcher(
            enabled=True,
            token=SecretStr("secret-telegram-token-do-not-log"),
            chat_id="@QuantForgSignals",
            sender=sender,
        )
        reset_telegram_dispatcher_for_tests(disp)
        emit_telegram(SIGNAL_GENERATED, "sig:keep", "hello")
        assert disp.pending == 1

    def test_notify_cycle_fans_out_without_requiring_jimvio(self) -> None:
        reset_jimvio_publisher_for_tests(None)
        sent: list[str] = []

        class _Disp:
            enabled = True

            def emit(self, event: str, event_id: str, text: str) -> None:
                sent.append(event)

        reset_telegram_dispatcher_for_tests(_Disp())  # type: ignore[arg-type]
        cycle = type(
            "C",
            (),
            {
                "ok": True,
                "cycle_outcome": "aborted",
                "abort_reason": "MAX_POSITIONS_REACHED",
                "decision_action": "BUY",
                "forwarded_to_oms": False,
                "mt5_ticket": None,
                "oms_message": None,
                "decision_reasons": (),
                "safety_failed_reasons": (),
                "detail": "",
                "broker_retcode": None,
            },
        )()
        decision = type(
            "D",
            (),
            {
                "symbol": "EURUSD",
                "direction": "BUY",
                "action": "BUY",
                "confidence": 80,
                "estimated_rr": None,
                "entry_zone": None,
                "stop_zone": None,
                "target_zone": None,
                "approved_lots": None,
            },
        )()
        notify_cycle(cycle, decision=decision, pipeline=None)
        assert SIGNAL_GENERATED in sent or "RISK_BLOCKED" in sent


@pytest.mark.unit
def test_settings_secret_not_dumped_as_plaintext() -> None:
    settings = Settings(
        _env_file=None,
        secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
        app_env=AppEnvironment.TESTING,
        jimvio_enabled=True,
        quantforg_webhook_secret=SecretStr(SECRET),
    )
    dumped = str(settings.model_dump())
    assert SECRET not in dumped
    assert settings.jimvio_webhook_url == DEFAULT_JIMVIO_WEBHOOK_URL


@pytest.mark.unit
def test_emit_jimvio_noop_without_publisher() -> None:
    reset_jimvio_publisher_for_tests(None)
    emit_jimvio("SYSTEM_ERROR", "sys:none", "x")
