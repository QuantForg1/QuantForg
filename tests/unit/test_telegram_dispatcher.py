"""Telegram dispatcher — fail-open observability, never on the trading path."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.application.services import telegram_dispatcher as dispatcher_mod
from app.application.services.telegram_dispatcher import (
    TelegramDispatcher,
    emit_telegram,
    notify_connectivity,
    notify_cycle,
    notify_pme,
    redact_secrets,
    reset_telegram_dispatcher_for_tests,
)
from app.application.services.telegram_events import (
    BREAKEVEN_SET,
    OMS_REJECTED,
    PARTIAL_CLOSE,
    RISK_BLOCKED,
    SIGNAL_CONFIRMED,
    SIGNAL_GENERATED,
    STOP_LOSS,
    TAKE_PROFIT,
    TRADE_CLOSED,
    TRADE_OPENED,
    TRAILING_STOP_UPDATED,
    classify_close_event,
    classify_cycle_notices,
    classify_pme_notices,
    format_test_message,
    format_trade_opened,
    opportunity_score_above_70,
    public_channel_notices,
)
from app.application.services.telegram_thread_store import (
    drop_telegram_threads_cache,
    reset_telegram_threads_for_tests,
)
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    ManageOutcome,
    PositionLifecycleState,
    PositionManageRecord,
    PositionManageResult,
)
from core.config.settings import AppEnvironment, Settings

REPO = Path(__file__).resolve().parents[2]
TOKEN = "secret-telegram-token-do-not-log"


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text or '{"ok":true,"result":{"message_id":1001}}'
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        try:
            data = json.loads(self.text)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}


@dataclass
class _Cycle:
    ok: bool = True
    trace_id: str | None = "t1"
    mode: str = "LIVE"
    decision_action: str | None = "BUY"
    forwarded_to_oms: bool = False
    detail: str = ""
    cycle_outcome: str = "aborted"
    abort_reason: str | None = None
    decision_reasons: tuple[str, ...] = ()
    safety_failed_reasons: tuple[str, ...] = ()
    mt5_ticket: int | None = None
    broker_retcode: int | None = None
    oms_message: str | None = None
    signal_id: str | None = None


@dataclass
class _Decision:
    action: str = "BUY"
    direction: str = "BUY"
    symbol: str = "EURJPY"
    confidence: int = 82
    approved_lots: Decimal = Decimal("0.01")
    estimated_rr: Decimal = Decimal("2.0")
    entry_zone: Any = None
    stop_zone: Any = None
    target_zone: Any = None


@dataclass
class _Zone:
    low: Decimal
    high: Decimal
    mid: Decimal | None = None


@dataclass
class _Journal:
    mt5_ticket: int | None = None
    mt5_deal: int | None = None
    retcode: int | None = None
    approved_lots: Decimal | None = None
    comment: str = ""


@dataclass
class _Bridge:
    journal_entry: _Journal | None = None
    oms_result: Any = None
    abort_reason: str = "none"


@dataclass
class _Pipeline:
    _last_ai_score: dict[str, Any]


@pytest.fixture(autouse=True)
def _reset_dispatcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "QUANTFORG_TELEGRAM_THREADS_PATH",
        str(tmp_path / "telegram_threads.json"),
    )
    reset_telegram_threads_for_tests()
    reset_telegram_dispatcher_for_tests(None)
    yield
    reset_telegram_dispatcher_for_tests(None)
    reset_telegram_threads_for_tests()


async def _unused_sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
    del url, payload
    return _FakeResponse(200)


def _dispatcher(
    sender: Any,
    *,
    enabled: bool = True,
    token: str | None = TOKEN,
    chat_id: str = "@QuantForgSignals",
) -> TelegramDispatcher:
    disp = TelegramDispatcher(
        enabled=enabled,
        token=SecretStr(token) if token else None,
        chat_id=chat_id,
        sender=sender,
        max_attempts=3,
        timeout_seconds=0.2,
    )
    reset_telegram_dispatcher_for_tests(disp)
    return disp


@pytest.mark.unit
@pytest.mark.trading_core
class TestTelegramDispatcher:
    @pytest.mark.asyncio
    async def test_success_send(self) -> None:
        captured: list[tuple[str, dict[str, Any]]] = []

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            captured.append((url, payload))
            return _FakeResponse(200, '{"ok":true}')

        disp = _dispatcher(sender)
        disp.emit_test()
        await disp.flush()
        assert captured
        assert captured[0][1]["chat_id"] == "@QuantForgSignals"
        assert "QUANTFORG TELEGRAM TEST" in captured[0][1]["text"]
        assert TOKEN in captured[0][0]
        assert disp.last_success is True

    @pytest.mark.asyncio
    async def test_timeout_does_not_raise(self) -> None:
        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            raise httpx.TimeoutException("timed out")

        disp = _dispatcher(sender)
        disp.emit("TRADE_OPENED", "open:1", "hello")
        await disp.flush()
        assert disp.last_success is False

    @pytest.mark.asyncio
    async def test_network_failure_does_not_raise(self) -> None:
        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            raise httpx.ConnectError("dns failure")

        disp = _dispatcher(sender)
        disp.emit("SYSTEM_ERROR", "sys:1", "err")
        await disp.flush()
        assert disp.last_success is False

    @pytest.mark.asyncio
    async def test_http_429_retries_then_fails_open(self) -> None:
        hits = {"n": 0}

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            hits["n"] += 1
            return _FakeResponse(429, "too many", headers={"Retry-After": "0"})

        disp = _dispatcher(sender)
        disp.emit("SIGNAL_GENERATED", "sig:1", "sig")
        await disp.flush(wait_seconds=8)
        assert hits["n"] == 3
        assert disp.last_success is False

    @pytest.mark.asyncio
    async def test_http_500_retries(self) -> None:
        hits = {"n": 0}

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            hits["n"] += 1
            return _FakeResponse(500, "oops")

        disp = _dispatcher(sender)
        disp.emit("SYSTEM_ERROR", "sys:500", "err")
        await disp.flush(wait_seconds=8)
        assert hits["n"] == 3

    def test_disabled_is_noop(self) -> None:
        called = {"n": 0}

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            called["n"] += 1
            return _FakeResponse(200)

        disp = _dispatcher(sender, enabled=False)
        disp.emit_test()
        assert disp.pending == 0
        assert called["n"] == 0

    def test_missing_token_disables(self) -> None:
        disp = TelegramDispatcher(
            enabled=True,
            token=None,
            chat_id="@QuantForgSignals",
        )
        assert disp.enabled is False
        disp.emit_test()
        assert disp.pending == 0

    def test_missing_chat_id_disables(self) -> None:
        disp = TelegramDispatcher(
            enabled=True,
            token=SecretStr(TOKEN),
            chat_id="",
        )
        assert disp.enabled is False

    def test_secret_never_in_redacted_logs(self) -> None:
        raw = f"POST https://api.telegram.org/bot{TOKEN}/sendMessage failed"
        assert TOKEN not in redact_secrets(raw, TOKEN)
        assert "***" in redact_secrets(raw, TOKEN)

    def test_httpx_log_filter_redacts_bot_url(self) -> None:
        from app.application.services.telegram_dispatcher import (
            _TelegramUrlRedactFilter,
        )

        filt = _TelegramUrlRedactFilter()
        record = logging.LogRecord(
            name="httpx",
            level=logging.INFO,
            pathname="x",
            lineno=1,
            msg="HTTP Request: %s %s",
            args=(
                "POST",
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            ),
            exc_info=None,
        )
        assert filt.filter(record) is True
        rendered = record.getMessage()
        assert TOKEN not in rendered
        assert "api.telegram.org/bot***" in rendered

    def test_duplicate_event_suppressed(self) -> None:
        disp = _dispatcher(_unused_sender)
        disp.emit("TRADE_OPENED", "open:575929789", "first")
        disp.emit("TRADE_OPENED", "open:575929789", "second")
        assert disp.pending == 1

    def test_emit_never_raises(self) -> None:
        disp = TelegramDispatcher(enabled=True, token=SecretStr(TOKEN), chat_id="@x")

        def boom(*_a: object, **_k: object) -> bool:
            raise RuntimeError("queue exploded")

        disp._already_seen = boom  # type: ignore[method-assign]
        disp.emit("TRADE_OPENED", "open:9", "x")

    def test_settings_aliases(self) -> None:
        settings = Settings(
            _env_file=None,
            secret_key="test-secret-key-that-is-long-enough-for-validation-32chars",
            app_env=AppEnvironment.TESTING,
            telegram_enabled=True,
            telegram_bot_token=SecretStr(TOKEN),
            telegram_chat_id="@QuantForgSignals",
        )
        assert settings.telegram_enabled is True
        assert settings.telegram_chat_id == "@QuantForgSignals"
        dumped = settings.model_dump()
        token_dump = dumped.get("telegram_bot_token")
        assert TOKEN not in str(token_dump)

    def test_format_test_message(self) -> None:
        text = format_test_message()
        assert "QUANTFORG TELEGRAM TEST" in text
        assert "NOT AFFECTED" in text


@pytest.mark.unit
@pytest.mark.trading_core
class TestTelegramEventTruth:
    def test_trade_opened_requires_ticket(self) -> None:
        cycle = _Cycle(decision_action="BUY", abort_reason="MT5_REJECTION")
        decision = _Decision()
        notices = classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=_Bridge(),
            pipeline=_Pipeline(
                {
                    "signal_action": "BUY",
                    "direction": "BUY",
                    "opportunity_score": 82,
                    "ai_confidence": 82,
                    "entry": "173.420",
                    "stop_loss": "173.080",
                    "take_profit": "174.100",
                    "expected_rr": "2.0",
                    "market_regime": "TRENDING",
                }
            ),
        )
        events = [row["event"] for row in notices]
        assert TRADE_OPENED not in events
        assert SIGNAL_GENERATED in events
        assert SIGNAL_CONFIRMED in events

    def test_trade_opened_after_real_ticket(self) -> None:
        cycle = _Cycle(
            decision_action="BUY",
            forwarded_to_oms=True,
            cycle_outcome="forwarded",
            abort_reason="none",
            mt5_ticket=575929789,
            broker_retcode=10009,
        )
        decision = _Decision(
            entry_zone=_Zone(Decimal("173.4"), Decimal("173.44"), Decimal("173.42")),
            stop_zone=_Zone(Decimal("173.08"), Decimal("173.08"), Decimal("173.08")),
            target_zone=_Zone(Decimal("174.1"), Decimal("174.1"), Decimal("174.1")),
        )
        notices = classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=_Bridge(journal_entry=_Journal(mt5_ticket=575929789, retcode=10009)),
            pipeline=_Pipeline({"signal_action": "BUY", "direction": "BUY"}),
        )
        opened = [row for row in notices if row["event"] == TRADE_OPENED]
        assert opened
        assert "575929789" in opened[0]["text"]
        assert "EXECUTED" in opened[0]["text"]

    def test_journal_ticket_used_when_cycle_ticket_missing(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(mt5_ticket=None, decision_action="BUY"),
            decision=_Decision(),
            bridge=_Bridge(journal_entry=_Journal(mt5_ticket=111)),
            pipeline=_Pipeline({"signal_action": "BUY"}),
        )
        assert any(row["event"] == TRADE_OPENED for row in notices)

    def test_risk_block_is_not_a_fill(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(
                decision_action="BUY",
                abort_reason="MAX_POSITIONS_REACHED",
                mt5_ticket=None,
            ),
            decision=_Decision(),
            pipeline=_Pipeline({"signal_action": "BUY", "direction": "BUY"}),
        )
        events = [row["event"] for row in notices]
        assert RISK_BLOCKED in events
        assert TRADE_OPENED not in events
        assert "No order submitted" in notices[-1]["text"]

    def test_oms_rejected(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(
                decision_action="BUY",
                abort_reason="OMS_FAILURE",
                oms_message="volume invalid",
            ),
            decision=_Decision(),
            pipeline=_Pipeline({"signal_action": "BUY"}),
        )
        assert any(row["event"] == OMS_REJECTED for row in notices)

    def test_waiting_cycle_is_silent(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(
                decision_action=None,
                cycle_outcome="waiting_next_cycle",
                abort_reason="NO_EXECUTABLE_SYMBOL",
            )
        )
        assert notices == []

    def test_breakeven_only_on_successful_sl_change(self) -> None:
        pos = ManagedPosition(
            ticket=10,
            symbol="EURJPY",
            side="buy",
            entry_price=Decimal("173.420"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("173.080"),
            risk_distance=Decimal("0.340"),
            opened_at=datetime.now(UTC),
            current_stop=Decimal("173.420"),
        )
        record = PositionManageRecord(
            ticket=10,
            action=ManageActionKind.BREAK_EVEN,
            from_state=PositionLifecycleState.OPEN,
            to_state=PositionLifecycleState.BE_MOVED,
            reason="Break-even",
            timestamp=pos.opened_at,
            latency_ms=1.0,
            outcome=ManageOutcome.SUCCESS,
            old_sl=Decimal("173.080"),
            new_sl=Decimal("173.420"),
            fingerprint="abc",
            symbol="EURJPY",
        )
        result = PositionManageResult(
            position=pos,
            action=ManageActionKind.BREAK_EVEN,
            record=record,
        )
        notices = classify_pme_notices(result=result)
        assert notices[0]["event"] == BREAKEVEN_SET
        assert "BREAKEVEN ACTIVE" in notices[0]["text"]

    def test_trailing_notification(self) -> None:
        pos = ManagedPosition(
            ticket=11,
            symbol="EURJPY",
            side="buy",
            entry_price=Decimal("173.420"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("173.420"),
            risk_distance=Decimal("0.340"),
            opened_at=datetime.now(UTC),
        )
        record = PositionManageRecord(
            ticket=11,
            action=ManageActionKind.TRAIL,
            from_state=PositionLifecycleState.BE_MOVED,
            to_state=PositionLifecycleState.TRAILING,
            reason="Trail",
            timestamp=pos.opened_at,
            latency_ms=1.0,
            outcome=ManageOutcome.SUCCESS,
            old_sl=Decimal("173.420"),
            new_sl=Decimal("173.680"),
            fingerprint="trail1",
        )
        notices = classify_pme_notices(
            result=PositionManageResult(
                position=pos,
                action=ManageActionKind.TRAIL,
                record=record,
            )
        )
        assert notices[0]["event"] == TRAILING_STOP_UPDATED

    def test_close_without_tp_sl_confirmation(self) -> None:
        assert classify_close_event("Manually closed or zero volume") == TRADE_CLOSED
        assert classify_close_event("TAKE PROFIT") == TAKE_PROFIT
        assert classify_close_event("STOP_LOSS") == STOP_LOSS

    def test_pme_duplicate_or_skip_silent(self) -> None:
        pos = ManagedPosition(
            ticket=12,
            symbol="EURJPY",
            side="buy",
            entry_price=Decimal("1"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("0.9"),
            risk_distance=Decimal("0.1"),
            opened_at=datetime.now(UTC),
        )
        result = PositionManageResult(
            position=pos,
            action=ManageActionKind.BREAK_EVEN,
            record=None,
            skipped=True,
        )
        assert classify_pme_notices(result=result) == []

    def test_notify_helpers_never_raise(self) -> None:
        reset_telegram_dispatcher_for_tests(None)
        notify_cycle(None)
        notify_pme(None)
        notify_connectivity(mt5_connected=True, gateway_available=True)
        emit_telegram("X", "x", "x")


@pytest.mark.unit
@pytest.mark.trading_core
class TestTelegramDoesNotBlockTrading:
    def test_frozen_modules_do_not_import_telegram(self) -> None:
        forbidden = (
            "app/infrastructure/brokers/mt5/gateway_client.py",
            "app/application/services/risk_engine.py",
            "app/domain/institutional_trading/ai_scalping/scoring.py",
            "app/domain/institutional_trading/management/policies.py",
            "app/domain/institutional_trading/execution/bridge.py",
        )
        for rel in forbidden:
            text = (REPO / rel).read_text(encoding="utf-8").lower()
            assert "telegram" not in text, rel
            assert "jimvio" not in text, rel

    @pytest.mark.asyncio
    async def test_telegram_failure_does_not_fail_notify_cycle(self) -> None:
        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            raise httpx.ConnectError("down")

        _dispatcher(sender)
        notify_cycle(
            _Cycle(mt5_ticket=99, decision_action="BUY", abort_reason="none"),
            decision=_Decision(),
            bridge=_Bridge(journal_entry=_Journal(mt5_ticket=99, retcode=10009)),
            pipeline=_Pipeline({"signal_action": "BUY"}),
        )
        await get_disp().flush()

    def test_format_opened_omits_fabricated_ticket(self) -> None:
        text = format_trade_opened(
            symbol="EURJPY",
            side="BUY",
            volume="0.01",
            entry="173.42",
            ticket=575000111,
        )
        assert "575000111" in text
        assert "EXECUTED" in text


def _exec_pipeline(**extra: Any) -> _Pipeline:
    payload: dict[str, Any] = {
        "signal_action": "BUY",
        "direction": "BUY",
        "opportunity_score": 87,
        "ai_confidence": 91,
        "entry": "1.08500",
        "stop_loss": "1.08200",
        "take_profit": "1.09400",
        "expected_rr": "3.0",
        "market_regime": "TRENDING",
    }
    payload.update(extra)
    return _Pipeline(payload)


def _filled_cycle(
    *,
    ticket: int = 575929789,
    symbol: str = "EURUSD",
) -> tuple[Any, Any, Any]:
    del symbol
    cycle = _Cycle(
        decision_action="BUY",
        forwarded_to_oms=True,
        cycle_outcome="forwarded",
        abort_reason="none",
        mt5_ticket=ticket,
        broker_retcode=10009,
        signal_id="sig-eurusd-1",
    )
    decision = _Decision(
        symbol="EURUSD",
        entry_zone=_Zone(Decimal("1.085"), Decimal("1.085"), Decimal("1.085")),
        stop_zone=_Zone(Decimal("1.082"), Decimal("1.082"), Decimal("1.082")),
        target_zone=_Zone(Decimal("1.094"), Decimal("1.094"), Decimal("1.094")),
        estimated_rr=Decimal("3.0"),
        confidence=91,
    )
    bridge = _Bridge(journal_entry=_Journal(mt5_ticket=ticket, retcode=10009))
    return cycle, decision, bridge


def _pme_success(
    *,
    action: ManageActionKind,
    ticket: int = 575929789,
    old_sl: str = "1.08200",
    new_sl: str = "1.08500",
    to_state: PositionLifecycleState = PositionLifecycleState.BE_MOVED,
    reason: str = "Break-even",
    fingerprint: str = "be1",
    remaining: str = "0.01",
    volume: str | None = None,
    pnl: str | None = None,
    exit_reason: str | None = None,
) -> PositionManageResult:
    pos = ManagedPosition(
        ticket=ticket,
        symbol="EURUSD",
        side="buy",
        entry_price=Decimal("1.08500"),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal(remaining),
        initial_stop=Decimal(old_sl),
        risk_distance=Decimal("0.003"),
        opened_at=datetime.now(UTC),
        current_stop=Decimal(new_sl),
    )
    record = PositionManageRecord(
        ticket=ticket,
        action=action,
        from_state=PositionLifecycleState.OPEN,
        to_state=to_state,
        reason=reason,
        timestamp=pos.opened_at,
        latency_ms=1.0,
        outcome=ManageOutcome.SUCCESS,
        old_sl=Decimal(old_sl),
        new_sl=Decimal(new_sl),
        fingerprint=fingerprint,
        symbol="EURUSD",
        volume=Decimal(volume) if volume is not None else None,
        pnl=pnl,
        exit_reason=exit_reason,
    )
    return PositionManageResult(position=pos, action=action, record=record)


@pytest.mark.unit
@pytest.mark.trading_core
class TestPublicTelegramChannel:
    def test_score_70_is_not_public_execution(self) -> None:
        assert opportunity_score_above_70(70) is False
        assert opportunity_score_above_70(70.0) is False
        assert opportunity_score_above_70(65) is False
        assert opportunity_score_above_70(71) is True
        cycle, decision, bridge = _filled_cycle()
        notices = classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(opportunity_score=70),
        )
        assert public_channel_notices(notices) == []

    def test_score_above_70_can_be_execution_candidate(self) -> None:
        cycle, decision, bridge = _filled_cycle()
        notices = classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(opportunity_score=71),
        )
        public = public_channel_notices(notices)
        events = [row["event"] for row in public]
        assert SIGNAL_CONFIRMED in events
        assert TRADE_OPENED in events
        assert any(
            "READY FOR EXECUTION" in row["text"] or "EXECUTED" in row["text"]
            for row in public
        )

    def test_score_above_70_still_fails_invalid_setup(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(decision_action="NO_TRADE", mt5_ticket=None),
            decision=_Decision(action="NO_TRADE", direction="NONE"),
            pipeline=_exec_pipeline(opportunity_score=72, signal_action="NONE"),
        )
        assert public_channel_notices(notices) == []

    def test_score_above_70_still_fails_if_risk_rejects(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(
                decision_action="BUY",
                abort_reason="MAX_POSITIONS_REACHED",
                mt5_ticket=None,
            ),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=87),
        )
        events = [row["event"] for row in notices]
        assert RISK_BLOCKED in events
        assert TRADE_OPENED not in events
        assert public_channel_notices(notices) == []

    def test_score_above_70_still_fails_if_oms_rejects(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(
                decision_action="BUY",
                abort_reason="OMS_FAILURE",
                oms_message="volume invalid",
            ),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=87),
        )
        assert any(row["event"] == OMS_REJECTED for row in notices)
        assert public_channel_notices(notices) == []

    def test_research_only_is_not_public(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(decision_action=None, mt5_ticket=None, abort_reason="none"),
            decision=_Decision(action="NO_TRADE", direction="BUY"),
            pipeline=_exec_pipeline(opportunity_score=65, signal_action="BUY"),
        )
        events = [row["event"] for row in notices]
        assert SIGNAL_GENERATED in events or events == []
        assert TRADE_OPENED not in events
        assert public_channel_notices(notices) == []

    def test_rejected_and_no_trade_noise_is_not_public(self) -> None:
        for abort in (
            "MAX_POSITIONS_REACHED",
            "MIN_LOT",
            "SPREAD_TOO_HIGH",
            "PYRAMIDING_BLOCKED",
            "NO_EXECUTABLE_SYMBOL",
        ):
            notices = classify_cycle_notices(
                cycle=_Cycle(
                    decision_action="BUY",
                    abort_reason=abort,
                    mt5_ticket=None,
                ),
                decision=_Decision(),
                pipeline=_exec_pipeline(),
            )
            assert public_channel_notices(notices) == []

    def test_executed_requires_real_ticket(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(decision_action="BUY", mt5_ticket=None, abort_reason="none"),
            decision=_Decision(),
            pipeline=_exec_pipeline(),
        )
        public = public_channel_notices(notices)
        assert TRADE_OPENED not in [row["event"] for row in public]
        cycle, decision, bridge = _filled_cycle(ticket=888111)
        filled = classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(),
        )
        public = public_channel_notices(filled)
        opened = [row for row in public if row["event"] == TRADE_OPENED]
        assert opened
        assert "888111" in opened[0]["text"]
        assert "EXECUTED" in opened[0]["text"]

    def test_pme_without_success_is_silent(self) -> None:
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
        assert classify_pme_notices(result=failed) == []
        assert public_channel_notices([]) == []

    def test_lifecycle_event_ids_are_stable(self) -> None:
        be = classify_pme_notices(
            result=_pme_success(action=ManageActionKind.BREAK_EVEN)
        )
        assert be[0]["event_id"].startswith("be:575929789:")
        trail = classify_pme_notices(
            result=_pme_success(
                action=ManageActionKind.TRAIL,
                to_state=PositionLifecycleState.TRAILING,
                fingerprint="trail1",
                old_sl="1.08500",
                new_sl="1.08600",
            )
        )
        assert trail[0]["event"] == TRAILING_STOP_UPDATED
        assert trail[0]["event_id"].startswith("trail:575929789:")
        partial = classify_pme_notices(
            result=_pme_success(
                action=ManageActionKind.PARTIAL_CLOSE,
                to_state=PositionLifecycleState.PARTIAL,
                fingerprint="deal-9",
                remaining="0.005",
                volume="0.005",
                pnl="12.5",
                old_sl="1.08500",
                new_sl="1.08500",
            )
        )
        assert partial[0]["event"] == PARTIAL_CLOSE
        assert partial[0]["event_id"] == "partial:575929789:deal-9"
        closed = classify_pme_notices(
            result=_pme_success(
                action=ManageActionKind.EMERGENCY_EXIT,
                to_state=PositionLifecycleState.EXITED,
                fingerprint="tp-1",
                exit_reason="TAKE_PROFIT",
                old_sl="1.08500",
                new_sl="1.08500",
            )
        )
        assert closed[-1]["event"] == TAKE_PROFIT
        sl_hit = classify_pme_notices(
            result=_pme_success(
                action=ManageActionKind.EMERGENCY_EXIT,
                to_state=PositionLifecycleState.EXITED,
                fingerprint="sl-1",
                exit_reason="STOP_LOSS",
                old_sl="1.08500",
                new_sl="1.08500",
            )
        )
        assert sl_hit[-1]["event"] == STOP_LOSS
        other = classify_pme_notices(
            result=_pme_success(
                action=ManageActionKind.EMERGENCY_EXIT,
                to_state=PositionLifecycleState.EXITED,
                fingerprint="man-1",
                exit_reason="Manually closed",
                old_sl="1.08500",
                new_sl="1.08500",
            )
        )
        assert other[-1]["event"] == TRADE_CLOSED

    def test_notify_cycle_research_does_not_enqueue_telegram(self) -> None:
        disp = _dispatcher(_unused_sender)
        notify_cycle(
            _Cycle(decision_action="BUY", mt5_ticket=None),
            decision=_Decision(),
            pipeline=_exec_pipeline(opportunity_score=65),
        )
        assert disp.pending == 0

    def test_notify_cycle_risk_block_does_not_enqueue_telegram(self) -> None:
        disp = _dispatcher(_unused_sender)
        notify_cycle(
            _Cycle(
                decision_action="BUY",
                abort_reason="MAX_POSITIONS_REACHED",
                mt5_ticket=None,
            ),
            decision=_Decision(),
            pipeline=_exec_pipeline(),
        )
        assert disp.pending == 0

    @pytest.mark.asyncio
    async def test_fill_posts_signal_and_opened(self) -> None:
        captured: list[dict[str, Any]] = []

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            captured.append(payload)
            n = 10 + len(captured)
            return _FakeResponse(
                200,
                json.dumps({"ok": True, "result": {"message_id": n}}),
            )

        disp = _dispatcher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle,
            decision=decision,
            bridge=bridge,
            pipeline=_exec_pipeline(),
        )
        await disp.flush()
        texts = [row["text"] for row in captured]
        assert any("QUANTFORG SIGNAL" in text for text in texts)
        assert any("QUANTFORG TRADE OPENED" in text for text in texts)
        assert any("575929789" in text for text in texts)
        assert captured[1].get("reply_to_message_id") == 11

    @pytest.mark.asyncio
    async def test_breakeven_replies_to_original_after_broker_success(self) -> None:
        captured: list[dict[str, Any]] = []

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            captured.append(payload)
            n = 20 + len(captured)
            return _FakeResponse(
                200,
                json.dumps({"ok": True, "result": {"message_id": n}}),
            )

        disp = _dispatcher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        await disp.flush()
        notify_pme(_pme_success(action=ManageActionKind.BREAK_EVEN))
        await disp.flush()
        be = [row for row in captured if "QUANTFORG BREAKEVEN" in row["text"]]
        assert be
        assert be[0]["reply_to_message_id"] == 21
        assert "BREAKEVEN ACTIVE" in be[0]["text"]

    @pytest.mark.asyncio
    async def test_lifecycle_replies_only_after_broker_success(self) -> None:
        captured: list[dict[str, Any]] = []

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            captured.append(payload)
            n = 30 + len(captured)
            return _FakeResponse(
                200,
                json.dumps({"ok": True, "result": {"message_id": n}}),
            )

        disp = _dispatcher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        await disp.flush()
        root_id = 31
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
        await disp.flush()
        trail = next(row for row in captured if "TRAILING STOP" in row["text"])
        partial = next(row for row in captured if "PARTIAL CLOSE" in row["text"])
        tp = next(row for row in captured if "TAKE PROFIT" in row["text"])
        assert trail["reply_to_message_id"] == root_id
        assert partial["reply_to_message_id"] == root_id
        assert tp["reply_to_message_id"] == root_id

    @pytest.mark.asyncio
    async def test_duplicate_lifecycle_deduped(self) -> None:
        captured: list[dict[str, Any]] = []

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            captured.append(payload)
            return _FakeResponse(200, '{"ok":true,"result":{"message_id":40}}')

        disp = _dispatcher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        await disp.flush()
        opened = [row for row in captured if "TRADE OPENED" in row["text"]]
        assert len(opened) == 1

    @pytest.mark.asyncio
    async def test_restart_does_not_duplicate_lifecycle(self) -> None:
        captured: list[dict[str, Any]] = []

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            captured.append(payload)
            return _FakeResponse(200, '{"ok":true,"result":{"message_id":50}}')

        disp = _dispatcher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        await disp.flush()
        first = len(captured)
        drop_telegram_threads_cache()
        disp2 = _dispatcher(sender)
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        await disp2.flush()
        assert len(captured) == first

    @pytest.mark.asyncio
    async def test_telegram_failure_does_not_block_or_stop_worker(self) -> None:
        hits = {"n": 0}

        async def sender(url: str, payload: dict[str, Any]) -> _FakeResponse:
            hits["n"] += 1
            raise httpx.ConnectError("down")

        disp = _dispatcher(sender)
        cycle, decision, bridge = _filled_cycle()
        notify_cycle(
            cycle, decision=decision, bridge=bridge, pipeline=_exec_pipeline()
        )
        notify_cycle(
            _Cycle(abort_reason="MAX_POSITIONS_REACHED", decision_action="BUY"),
            decision=_Decision(),
            pipeline=_exec_pipeline(),
        )
        await disp.flush()
        assert hits["n"] >= 1
        assert disp.last_success is False

    def test_multi_market_symbols_are_public_when_filled(self) -> None:
        for symbol in ("EURUSD", "GBPUSD", "XAGUSD", "BTCUSD"):
            cycle = _Cycle(
                decision_action="BUY",
                mt5_ticket=100 + len(symbol),
                abort_reason="none",
                broker_retcode=10009,
            )
            decision = _Decision(symbol=symbol)
            notices = classify_cycle_notices(
                cycle=cycle,
                decision=decision,
                bridge=_Bridge(
                    journal_entry=_Journal(
                        mt5_ticket=100 + len(symbol), retcode=10009
                    )
                ),
                pipeline=_exec_pipeline(),
            )
            public = public_channel_notices(notices)
            assert TRADE_OPENED in [row["event"] for row in public], symbol
            assert symbol in public[0]["text"]

    def test_cycle_timeout_stays_quiet(self) -> None:
        notices = classify_cycle_notices(
            cycle=_Cycle(abort_reason="CYCLE_TIMEOUT", decision_action="BUY")
        )
        assert notices == []
        assert public_channel_notices(notices) == []


def get_disp() -> TelegramDispatcher:
    disp = dispatcher_mod.get_telegram_dispatcher()
    assert disp is not None
    return disp
