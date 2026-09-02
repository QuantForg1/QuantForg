"""Jimvio webhook publisher — HMAC, fail-open, never on the trading path."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
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
    notify_connectivity,
    notify_cycle,
    notify_pme,
    notify_robot_started,
    notify_system_error,
    reset_telegram_dispatcher_for_tests,
)
from app.application.services.telegram_events import (
    SIGNAL_GENERATED,
    TRADE_OPENED,
)
from app.application.services.telegram_thread_store import (
    reset_telegram_threads_for_tests,
)
from core.config.settings import AppEnvironment, Settings

SECRET = "jimvio-test-secret-do-not-log"


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.headers: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _reset_publishers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "QUANTFORG_TELEGRAM_THREADS_PATH",
        str(tmp_path / "telegram_threads.json"),
    )
    reset_telegram_threads_for_tests()
    reset_jimvio_publisher_for_tests(None)
    reset_telegram_dispatcher_for_tests(None)
    yield
    reset_jimvio_publisher_for_tests(None)
    reset_telegram_dispatcher_for_tests(None)
    reset_telegram_threads_for_tests()


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

    def test_python_hmac_matches_node_crypto_hex(self) -> None:
        """Jimvio verifies HMAC-SHA256 hex of the raw body (Node crypto)."""
        import base64
        import shutil
        import subprocess

        payload = {
            "event_id": "quantforg-e2e-hmac",
            "event_type": "SYSTEM_ERROR",
            "status": "TEST",
        }
        body, signature = signed_request(payload, SECRET)
        if shutil.which("node") is None:
            expected = hmac.new(
                SECRET.encode("utf-8"), body, hashlib.sha256
            ).hexdigest()
            assert signature == expected
            return
        encoded = base64.b64encode(body).decode("ascii")
        script = (
            "const crypto=require('crypto');"
            "const secret=process.env.QF_HMAC_SECRET;"
            "const body=Buffer.from(process.env.QF_HMAC_BODY,'base64');"
            "process.stdout.write("
            "crypto.createHmac('sha256',secret).update(body).digest('hex')"
            ");"
        )
        env = {
            **__import__("os").environ,
            "QF_HMAC_SECRET": SECRET,
            "QF_HMAC_BODY": encoded,
        }
        node_bin = shutil.which("node")
        assert node_bin is not None
        node = subprocess.run(  # noqa: S603
            [node_bin, "-e", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        assert node.stdout.strip() == signature
        assert SECRET not in node.stdout

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
        assert opened["status"] == "ACTIVE"
        assert "mt5_ticket" not in opened["metadata"]
        ghost = build_jimvio_payload(
            event=TRADE_OPENED,
            event_id="open:missing",
            fields={"symbol": "USDJPY", "direction": "BUY"},
        )
        assert ghost is not None
        assert ghost["event_type"] == "TRADE_REJECTED"
        assert ghost["status"] == "REJECTED"

    def test_confirmed_fill_is_executed_with_ticket_metadata(self) -> None:
        payload = build_jimvio_payload(
            event="SIGNAL_CONFIRMED",
            event_id="signal:sig-eurusd-1",
            message="QUANTFORG SIGNAL",
            fields={
                "symbol": "EURUSD",
                "direction": "BUY",
                "entry": "1.08500",
                "stop_loss": "1.08200",
                "take_profit": "1.09400",
                "ticket": 575929789,
                "opportunity": 87,
                "confidence": 91,
                "risk_reward": "3.0",
                "regime": "TRENDING",
                "signal_id": "sig-eurusd-1",
            },
        )
        assert payload is not None
        assert payload["event_type"] == "SIGNAL_CONFIRMED"
        assert payload["status"] == "CONFIRMED"
        assert "mt5_ticket" not in payload["metadata"]
        assert payload["metadata"]["opportunity"] == 87
        assert payload["metadata"]["signal_id"] == "sig-eurusd-1"

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

            def emit(self, event: str, event_id: str, text: str, **kwargs: Any) -> None:
                del kwargs
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
        assert sent == []


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
def test_settings_accepts_jimvio_webhook_secret_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUANTFORG_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("JIMVIO_WEBHOOK_SECRET", SECRET)
    settings = Settings(
        _env_file=None,
        secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
        app_env=AppEnvironment.TESTING,
        jimvio_enabled=True,
    )
    configured = settings.quantforg_webhook_secret
    assert configured is not None
    assert configured.get_secret_value() == SECRET


@pytest.mark.unit
def test_emit_jimvio_noop_without_publisher() -> None:
    reset_jimvio_publisher_for_tests(None)
    emit_jimvio("SYSTEM_ERROR", "sys:none", "x")


@pytest.mark.unit
@pytest.mark.trading_core
class TestJimvioMatchesTelegramPublicFilter:
    def _wire(self) -> tuple[JimvioPublisher, list[dict[str, Any]], list[str]]:
        telegram_ids: list[str] = []

        class _Disp:
            enabled = True
            pending = 0

            def emit(self, event: str, event_id: str, text: str, **kwargs: Any) -> None:
                del event, text, kwargs
                telegram_ids.append(event_id)
                self.pending += 1

        reset_telegram_dispatcher_for_tests(_Disp())  # type: ignore[arg-type]
        bodies: list[dict[str, Any]] = []

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            del url, headers
            bodies.append(json.loads(body.decode()))
            return _FakeResponse(200)

        pub = _publisher(sender)
        return pub, bodies, telegram_ids

    def test_p_at_or_below_70_is_quiet_on_both(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _Cycle,
            _Decision,
            _exec_pipeline,
        )

        pub, _bodies, telegram_ids = self._wire()
        notify_cycle(
            _Cycle(decision_action="BUY", mt5_ticket=None),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=65),
        )
        notify_cycle(
            _Cycle(decision_action="BUY", mt5_ticket=None),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=70),
        )
        assert pub.pending == 0
        assert telegram_ids == []

    def test_invalid_strategy_is_quiet_on_both(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _Cycle,
            _Decision,
            _exec_pipeline,
        )

        pub, _bodies, telegram_ids = self._wire()
        notify_cycle(
            _Cycle(decision_action="NO_TRADE", mt5_ticket=None),
            decision=_Decision(action="NO_TRADE", direction="NONE"),
            pipeline=_exec_pipeline(opportunity_score=72, signal_action="NONE"),
        )
        assert pub.pending == 0
        assert telegram_ids == []

    def test_risk_and_oms_rejection_are_quiet_on_both(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _Cycle,
            _Decision,
            _exec_pipeline,
        )

        pub, _bodies, telegram_ids = self._wire()
        notify_cycle(
            _Cycle(
                decision_action="BUY",
                abort_reason="MAX_POSITIONS_REACHED",
                mt5_ticket=None,
            ),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=87),
        )
        notify_cycle(
            _Cycle(
                decision_action="BUY",
                abort_reason="OMS_FAILURE",
                oms_message="volume invalid",
            ),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=87),
        )
        assert pub.pending == 0
        assert telegram_ids == []

    def test_no_ticket_is_not_executed_on_either(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _Cycle,
            _Decision,
            _exec_pipeline,
        )

        pub, _bodies, telegram_ids = self._wire()
        notify_cycle(
            _Cycle(decision_action="BUY", mt5_ticket=None, abort_reason="none"),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=87),
        )
        assert pub.pending == 0
        assert telegram_ids == []

    @pytest.mark.asyncio
    async def test_real_ticket_sends_identical_verified_event_ids(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _exec_pipeline,
            _filled_cycle,
        )

        pub, bodies, telegram_ids = self._wire()
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(opportunity_score=87),
        )
        await pub.flush()
        jimvio_ids = [row["event_id"] for row in bodies]
        assert telegram_ids == jimvio_ids
        assert "signal:sig-eurusd-1" in jimvio_ids
        assert "open:575929789" in jimvio_ids
        types = {row["event_type"] for row in bodies}
        assert "SIGNAL_DETECTED" not in types
        assert "RISK_REJECTED" not in types
        opened = next(row for row in bodies if row["event_id"] == "open:575929789")
        assert opened["status"] == "ACTIVE"
        assert "mt5_ticket" not in opened["metadata"]
        assert "Volume:" not in (opened.get("message") or "")
        assert "MT5 Ticket" not in (opened.get("message") or "")
        confirmed = next(
            row for row in bodies if row["event_id"] == "signal:sig-eurusd-1"
        )
        assert confirmed["status"] == "CONFIRMED"
        assert confirmed["symbol"] == "EURUSD"
        assert confirmed["direction"] == "BUY"
        assert confirmed["metadata"]["opportunity"] == 87
        assert confirmed["message"]
        assert opened["message"]
        assert "QUANTFORG SIGNAL" in confirmed["message"]
        assert "TRADE ACTIVE" in opened["message"]
        assert confirmed["message"] != opened["message"]

    @pytest.mark.asyncio
    async def test_lifecycle_success_mirrors_to_both(self) -> None:
        from app.domain.institutional_trading.management.models import (
            ManageActionKind,
            PositionLifecycleState,
        )
        from tests.unit.test_telegram_dispatcher import (
            _exec_pipeline,
            _filled_cycle,
            _pme_success,
        )

        pub, bodies, telegram_ids = self._wire()
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(),
        )
        notify_pme(_pme_success(action=ManageActionKind.BREAK_EVEN))
        notify_pme(
            _pme_success(
                action=ManageActionKind.TRAIL,
                to_state=PositionLifecycleState.TRAILING,
                fingerprint="t1",
                old_sl="1.08500",
                new_sl="1.08620",
            )
        )
        notify_pme(
            _pme_success(
                action=ManageActionKind.PARTIAL_CLOSE,
                to_state=PositionLifecycleState.PARTIAL,
                fingerprint="p1",
                remaining="0.005",
                volume="0.005",
                pnl="4.2",
                old_sl="1.08500",
                new_sl="1.08500",
            )
        )
        notify_pme(
            _pme_success(
                action=ManageActionKind.EMERGENCY_EXIT,
                to_state=PositionLifecycleState.EXITED,
                fingerprint="tp1",
                exit_reason="TAKE_PROFIT",
                pnl="18.0",
                old_sl="1.08500",
                new_sl="1.08500",
            )
        )
        await pub.flush()
        assert telegram_ids == [row["event_id"] for row in bodies]
        kinds = {row["event_type"] for row in bodies}
        assert "BREAKEVEN_SET" in kinds
        assert "TRAILING_STOP_UPDATED" in kinds
        assert "PARTIAL_CLOSE" in kinds
        assert "TAKE_PROFIT_HIT" in kinds

    def test_failed_pme_and_ops_noise_stay_off_jimvio(self) -> None:
        from datetime import UTC, datetime
        from decimal import Decimal

        from app.domain.institutional_trading.management.models import (
            ManageActionKind,
            ManagedPosition,
            ManageOutcome,
            PositionLifecycleState,
            PositionManageRecord,
            PositionManageResult,
        )

        pub, _bodies, telegram_ids = self._wire()
        pos = ManagedPosition(
            ticket=10,
            symbol="EURUSD",
            side="buy",
            entry_price=Decimal("1.08"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("1.07"),
            risk_distance=Decimal("0.01"),
            opened_at=datetime.now(UTC),
        )
        failed = PositionManageResult(
            position=pos,
            action=ManageActionKind.BREAK_EVEN,
            record=PositionManageRecord(
                ticket=10,
                action=ManageActionKind.BREAK_EVEN,
                from_state=PositionLifecycleState.OPEN,
                to_state=PositionLifecycleState.OPEN,
                reason="no-op",
                timestamp=pos.opened_at,
                latency_ms=1.0,
                outcome=ManageOutcome.ABORTED,
                fingerprint="nope",
            ),
        )
        notify_pme(failed)
        notify_system_error(reason="boom")
        notify_connectivity(mt5_connected=True, gateway_available=False)
        assert pub.pending == 0
        assert telegram_ids == []
        notify_robot_started()
        assert telegram_ids == ["public:status:READY"]
        assert pub.pending == 1

    @pytest.mark.asyncio
    async def test_duplicate_fill_is_not_reposted(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _exec_pipeline,
            _filled_cycle,
        )

        pub, bodies, _telegram_ids = self._wire()
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(),
        )
        notify_cycle(
            cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(),
        )
        await pub.flush()
        opened = [row for row in bodies if row["event_id"] == "open:575929789"]
        assert len(opened) == 1

    @pytest.mark.asyncio
    async def test_jimvio_outage_does_not_block_telegram_or_trading(self) -> None:
        from tests.unit.test_telegram_dispatcher import (
            _exec_pipeline,
            _filled_cycle,
        )

        telegram_ids: list[str] = []

        class _Disp:
            enabled = True
            pending = 0

            def emit(self, event: str, event_id: str, text: str, **kwargs: Any) -> None:
                del event, text, kwargs
                telegram_ids.append(event_id)
                self.pending += 1

        reset_telegram_dispatcher_for_tests(_Disp())  # type: ignore[arg-type]

        async def sender(
            url: str, headers: dict[str, str], body: bytes
        ) -> _FakeResponse:
            del url, headers, body
            raise httpx.ConnectError("jimvio down")

        pub = _publisher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(),
        )
        await pub.flush(wait_seconds=8)
        assert telegram_ids
        assert pub.last_success is False
