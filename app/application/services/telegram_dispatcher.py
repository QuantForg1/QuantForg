"""Non-blocking Telegram Bot API dispatcher.

Fail-open observability: enqueue never raises into trading code.
HTTP happens on an isolated asyncio task — not inside order_send, Risk,
OMS, PME policy, or signal scoring.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.application.services.telegram_events import (
    TELEGRAM_TEST,
    format_test_message,
)
from app.application.services.telegram_thread_store import (
    bind_thread,
    lookup_message_id,
    mark_event_seen,
    persisted_seen_ids,
)
from core.logging import get_logger

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org"
_MAX_QUEUE = 64
_MAX_SEEN = 2048
_SEEN_TTL_SECONDS = 6 * 3600
_TIMEOUT_SECONDS = 4.0
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)[^/\s]+", re.IGNORECASE)


class TelegramSender(Protocol):
    async def __call__(self, url: str, payload: dict[str, Any]) -> httpx.Response: ...


def _secret_text(value: Any) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    raw = getter() if callable(getter) else str(value)
    text = str(raw or "").strip()
    return text or None


def _telegram_message_id(response: object) -> int | None:
    parser = getattr(response, "json", None)
    data: Any
    if callable(parser):
        try:
            data = parser()
        except Exception:
            data = None
    else:
        data = None
    if not isinstance(data, dict):
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip().startswith("{"):
            try:
                data = json.loads(text)
            except Exception:
                return None
        else:
            return None
    if data.get("ok") is False:
        return None
    result = data.get("result")
    if not isinstance(result, dict):
        return None
    try:
        mid = int(result.get("message_id"))
    except (TypeError, ValueError):
        return None
    return mid if mid > 0 else None


def redact_secrets(text: str, *secrets: str | None) -> str:
    redacted = _BOT_URL_RE.sub(r"\1***", text)
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def _safe_url_for_logs(url: str) -> str:
    redacted = _BOT_URL_RE.sub(r"\1***", url)
    parts = urlsplit(redacted)
    path = parts.path
    if "/bot" in path:
        head, _sep, tail = path.partition("/bot")
        token_and_rest = tail
        slash = token_and_rest.find("/")
        rest = token_and_rest[slash:] if slash >= 0 else ""
        path = f"{head}/bot***/{rest.lstrip('/')}"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _redact_log_value(value: object) -> object:
    text = str(value)
    if "api.telegram.org/bot" in text.lower():
        return _BOT_URL_RE.sub(r"\1***", text)
    return value


class _TelegramUrlRedactFilter(logging.Filter):
    """Prevent httpx/httpcore from logging the Bot API token in the URL."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            args = record.args
            if isinstance(args, dict):
                record.args = {k: _redact_log_value(v) for k, v in args.items()}
            elif isinstance(args, tuple):
                record.args = tuple(_redact_log_value(a) for a in args)
            elif args:
                record.args = _redact_log_value(args)
            if isinstance(record.msg, str) and "api.telegram.org" in record.msg:
                record.msg = _BOT_URL_RE.sub(r"\1***", record.msg)
        except Exception:
            return True
        return True


_httpx_filter_installed = False


def _install_httpx_telegram_redact_filter() -> None:
    global _httpx_filter_installed
    if _httpx_filter_installed:
        return
    redact = _TelegramUrlRedactFilter()
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).addFilter(redact)
    _httpx_filter_installed = True


@dataclass(frozen=True, slots=True)
class TelegramNotice:
    event: str
    event_id: str
    text: str
    reply_ticket: str | None = None
    bind_ticket: str | None = None
    bind_signal: str | None = None
    require_thread: bool = False


class TelegramDispatcher:
    """Bounded in-memory queue + isolated HTTP worker."""

    def __init__(
        self,
        *,
        enabled: bool,
        token: Any = None,
        chat_id: str | None = None,
        sender: TelegramSender | None = None,
        timeout_seconds: float = _TIMEOUT_SECONDS,
        max_attempts: int = _MAX_ATTEMPTS,
    ) -> None:
        self._enabled = bool(enabled)
        self._token = _secret_text(token)
        self._chat_id = str(chat_id or "").strip()
        self._sender = sender
        self._timeout = float(timeout_seconds)
        self._max_attempts = max(1, int(max_attempts))
        self._queue: deque[TelegramNotice] = deque()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._last_success = False
        try:
            for key in persisted_seen_ids():
                self._seen[key] = time.monotonic() + _SEEN_TTL_SECONDS
        except Exception:
            logger.exception("telegram_seen_restore_failed")
        if self._enabled and not (self._token and self._chat_id):
            self._enabled = False
            logger.warning(
                "telegram_disabled_missing_credentials",
                token_configured=bool(self._token),
                chat_id_configured=bool(self._chat_id),
            )
        if self._enabled:
            _install_httpx_telegram_redact_filter()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def configured(self) -> bool:
        return bool(self._token and self._chat_id)

    @property
    def last_success(self) -> bool:
        return self._last_success

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._queue)

    def emit(
        self,
        event: str,
        event_id: str,
        text: str,
        *,
        reply_ticket: str | None = None,
        bind_ticket: str | None = None,
        bind_signal: str | None = None,
        require_thread: bool = False,
    ) -> None:
        """Enqueue a notice. Never raises. Never awaits Telegram HTTP."""
        try:
            if not self._enabled:
                return
            key = str(event_id or "").strip() or f"{event}:{time.time_ns()}"
            notice = TelegramNotice(
                event=str(event),
                event_id=key,
                text=str(text),
                reply_ticket=str(reply_ticket).strip() if reply_ticket else None,
                bind_ticket=str(bind_ticket).strip() if bind_ticket else None,
                bind_signal=str(bind_signal).strip() if bind_signal else None,
                require_thread=bool(require_thread),
            )
            with self._lock:
                if self._already_seen(key):
                    logger.info(
                        "telegram_duplicate_suppressed",
                        telegram_event=notice.event,
                        event_id=key,
                    )
                    return
                self._mark_seen(key)
                if len(self._queue) >= _MAX_QUEUE:
                    dropped = self._queue.popleft()
                    logger.warning(
                        "telegram_queue_overflow_drop",
                        dropped_event=dropped.event,
                        telegram_event=notice.event,
                    )
                self._queue.append(notice)
            try:
                mark_event_seen(key)
            except Exception:
                logger.exception("telegram_seen_persist_failed")
        except Exception:
            logger.exception("telegram_emit_failed")

    def forget(self, event_id: str) -> None:
        """Allow a previously emitted id (e.g. robot restart) to notify again."""
        key = str(event_id or "").strip()
        if not key:
            return
        with self._lock:
            self._seen.pop(key, None)

    def emit_test(self) -> None:
        self.emit(TELEGRAM_TEST, "telegram:test", format_test_message())

    def start(self) -> None:
        if not self._enabled:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = loop.create_task(self._worker(), name="telegram-dispatcher")

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def flush(self, *, wait_seconds: float = 3.0) -> None:
        """Drain the queue (tests / shutdown). Never raises to caller."""
        try:
            deadline = time.monotonic() + max(0.05, float(wait_seconds))
            while time.monotonic() < deadline:
                with self._lock:
                    empty = not self._queue
                    notice = self._queue.popleft() if self._queue else None
                if notice is None:
                    if empty:
                        return
                    continue
                await self._deliver(notice)
        except Exception:
            logger.exception("telegram_flush_failed")

    def _already_seen(self, key: str) -> bool:
        now = time.monotonic()
        expires = self._seen.get(key)
        if expires is None:
            return False
        if expires <= now:
            self._seen.pop(key, None)
            return False
        self._seen.move_to_end(key)
        return True

    def _mark_seen(self, key: str) -> None:
        now = time.monotonic()
        stale = [item for item, exp in self._seen.items() if exp <= now]
        for item in stale:
            self._seen.pop(item, None)
        while len(self._seen) >= _MAX_SEEN:
            self._seen.popitem(last=False)
        self._seen[key] = now + _SEEN_TTL_SECONDS

    async def _worker(self) -> None:
        while self._running:
            notice: TelegramNotice | None = None
            with self._lock:
                if self._queue:
                    notice = self._queue.popleft()
            if notice is None:
                await asyncio.sleep(0.05)
                continue
            await self._deliver(notice)

    async def _deliver(self, notice: TelegramNotice) -> None:
        try:
            await self._send_with_retry(notice)
        except Exception as exc:
            self._last_success = False
            logger.warning(
                "telegram_notification_failed",
                telegram_event=notice.event,
                event_id=notice.event_id,
                error=redact_secrets(str(exc), self._token),
            )

    async def _send_with_retry(self, notice: TelegramNotice) -> None:
        if not self._token or not self._chat_id:
            return
        url = f"{_TELEGRAM_API}/bot{self._token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": notice.text,
            "disable_web_page_preview": True,
        }
        reply_id = None
        if notice.reply_ticket:
            try:
                reply_id = lookup_message_id(
                    ticket=notice.reply_ticket,
                    signal_id=notice.bind_signal,
                )
            except Exception:
                logger.exception("telegram_thread_lookup_failed")
                reply_id = None
        if notice.require_thread and reply_id is None:
            logger.info(
                "telegram_lifecycle_skipped_no_thread",
                telegram_event=notice.event,
                event_id=notice.event_id,
            )
            return
        if reply_id is not None:
            payload["reply_to_message_id"] = reply_id
        last_error = "unknown"
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._post(url, payload)
            except (httpx.TimeoutException, httpx.NetworkError, OSError) as exc:
                last_error = redact_secrets(f"{type(exc).__name__}: {exc}", self._token)
                if attempt >= self._max_attempts:
                    break
                await asyncio.sleep(
                    _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
                )
                continue
            except Exception as exc:
                last_error = redact_secrets(str(exc), self._token)
                break
            status = int(getattr(response, "status_code", 0) or 0)
            if 200 <= status < 300:
                self._last_success = True
                try:
                    mid = _telegram_message_id(response)
                    if mid is not None and (notice.bind_ticket or notice.bind_signal):
                        bind_thread(
                            message_id=mid,
                            ticket=notice.bind_ticket,
                            signal_id=notice.bind_signal,
                        )
                except Exception:
                    logger.exception("telegram_thread_bind_failed")
                logger.info(
                    "telegram_notification_sent",
                    telegram_event=notice.event,
                    event_id=notice.event_id,
                    status=status,
                    api=_safe_url_for_logs(url),
                )
                return
            body = redact_secrets(getattr(response, "text", "") or "", self._token)
            last_error = f"http_{status}"
            retryable = status == 429 or status >= 500
            if not retryable or attempt >= self._max_attempts:
                logger.warning(
                    "telegram_notification_failed",
                    telegram_event=notice.event,
                    event_id=notice.event_id,
                    status=status,
                    api=_safe_url_for_logs(url),
                    body=body[:240],
                )
                self._last_success = False
                return
            wait = _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
            if status == 429:
                retry_after = getattr(response, "headers", {}).get("Retry-After")
                try:
                    wait = min(8.0, float(retry_after))
                except (TypeError, ValueError):
                    wait = 2.0
            await asyncio.sleep(wait)
        self._last_success = False
        logger.warning(
            "telegram_notification_failed",
            telegram_event=notice.event,
            event_id=notice.event_id,
            error=last_error,
            api=_safe_url_for_logs(url),
        )

    async def _post(self, url: str, payload: dict[str, Any]) -> httpx.Response:
        if self._sender is not None:
            return await self._sender(url, payload)
        timeout = httpx.Timeout(self._timeout, connect=self._timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=payload)


_dispatcher: TelegramDispatcher | None = None
_dispatcher_lock = Lock()
_connectivity = {"mt5": None, "gateway": None}


def get_telegram_dispatcher() -> TelegramDispatcher | None:
    return _dispatcher


def reset_telegram_dispatcher_for_tests(
    dispatcher: TelegramDispatcher | None = None,
) -> TelegramDispatcher | None:
    global _dispatcher, _connectivity
    with _dispatcher_lock:
        _dispatcher = dispatcher
        _connectivity = {"mt5": None, "gateway": None}
    return _dispatcher


def emit_telegram(
    event: str,
    event_id: str,
    text: str,
    *,
    fields: dict[str, Any] | None = None,
    telegram: bool = True,
    jimvio: bool = True,
    reply_ticket: str | None = None,
    bind_ticket: str | None = None,
    bind_signal: str | None = None,
    require_thread: bool = False,
) -> None:
    """Process-wide fail-open emit. Safe to call from any trading observer.

    Telegram and Jimvio are independent delivery targets for the same
    verified public notice. Failure of one never blocks the other, Risk,
    OMS, MT5, or the ITE loop.
    """
    if telegram:
        try:
            dispatcher = get_telegram_dispatcher()
            if dispatcher is not None:
                dispatcher.emit(
                    event,
                    event_id,
                    text,
                    reply_ticket=reply_ticket,
                    bind_ticket=bind_ticket,
                    bind_signal=bind_signal,
                    require_thread=require_thread,
                )
        except Exception:
            logger.exception("telegram_emit_failed")
    if jimvio:
        try:
            from app.application.services.jimvio_publisher import emit_jimvio

            emit_jimvio(event, event_id, text, fields=fields)
        except Exception:
            logger.exception("jimvio_fanout_failed")


async def start_telegram_dispatcher(settings: Any) -> TelegramDispatcher:
    global _dispatcher
    dispatcher = TelegramDispatcher(
        enabled=bool(getattr(settings, "telegram_enabled", False)),
        token=getattr(settings, "telegram_bot_token", None),
        chat_id=getattr(settings, "telegram_chat_id", None),
    )
    with _dispatcher_lock:
        previous = _dispatcher
        _dispatcher = dispatcher
    if previous is not None:
        await previous.stop()
    dispatcher.start()
    if dispatcher.enabled:
        logger.info(
            "telegram_dispatcher_started",
            chat_id_configured=bool(dispatcher.configured),
            enabled=True,
        )
    else:
        logger.info("telegram_dispatcher_disabled")
    return dispatcher


async def stop_telegram_dispatcher() -> None:
    global _dispatcher
    with _dispatcher_lock:
        dispatcher = _dispatcher
        _dispatcher = None
    if dispatcher is not None:
        await dispatcher.stop()


def notify_connectivity(
    *,
    mt5_connected: bool | None,
    gateway_available: bool | None,
) -> None:
    """Emit MT5/gateway edge transitions only (not every health tick)."""
    from app.application.services.telegram_events import (
        GATEWAY_OFFLINE,
        GATEWAY_ONLINE,
        MT5_CONNECTED,
        MT5_DISCONNECTED,
        format_gateway_offline,
        format_gateway_online,
        format_mt5_connected,
        format_mt5_disconnected,
    )

    try:
        if mt5_connected is not None:
            previous = _connectivity.get("mt5")
            if previous is not bool(mt5_connected):
                _connectivity["mt5"] = bool(mt5_connected)
                if previous is not None or bool(mt5_connected):
                    if mt5_connected:
                        emit_telegram(
                            MT5_CONNECTED,
                            f"mt5:connected:{time.time_ns()}",
                            format_mt5_connected(),
                            telegram=False,
                            jimvio=False,
                        )
                    else:
                        emit_telegram(
                            MT5_DISCONNECTED,
                            f"mt5:disconnected:{time.time_ns()}",
                            format_mt5_disconnected(),
                            telegram=False,
                            jimvio=False,
                        )
        if gateway_available is not None:
            previous = _connectivity.get("gateway")
            if previous is not bool(gateway_available):
                _connectivity["gateway"] = bool(gateway_available)
                if previous is not None or bool(gateway_available):
                    if gateway_available:
                        emit_telegram(
                            GATEWAY_ONLINE,
                            f"gw:online:{time.time_ns()}",
                            format_gateway_online(),
                            telegram=False,
                            jimvio=False,
                        )
                    else:
                        emit_telegram(
                            GATEWAY_OFFLINE,
                            f"gw:offline:{time.time_ns()}",
                            format_gateway_offline(),
                            telegram=False,
                            jimvio=False,
                        )
    except Exception:
        logger.exception("telegram_connectivity_notify_failed")


def _emit_verified_public_notices(classified: list[dict[str, Any]]) -> None:
    """Fan the public Signals filter to Telegram and Jimvio together.

    Research, risk, OMS, and operational notices stay off both public
    destinations. Qualification lives in public_channel_notices only.
    """
    from app.application.services.telegram_events import public_channel_notices

    for notice in public_channel_notices(classified):
        fields = (
            notice.get("fields") if isinstance(notice.get("fields"), dict) else None
        )
        emit_telegram(
            notice["event"],
            notice["event_id"],
            notice["text"],
            fields=fields,
            reply_ticket=notice.get("reply_ticket"),
            bind_ticket=notice.get("bind_ticket"),
            bind_signal=notice.get("bind_signal"),
            require_thread=bool(notice.get("require_thread")),
        )


def notify_cycle(
    cycle: Any,
    *,
    decision: Any = None,
    bridge: Any = None,
    pipeline: Any = None,
) -> None:
    try:
        from app.application.services.telegram_events import classify_cycle_notices

        classified = classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=bridge,
            pipeline=pipeline,
        )
        _emit_verified_public_notices(classified)
    except Exception:
        logger.exception("telegram_cycle_notify_failed")


def notify_pme(result: Any, *, current_price: object = None) -> None:
    try:
        from app.application.services.telegram_events import classify_pme_notices

        classified = classify_pme_notices(
            result=result, current_price=current_price
        )
        _emit_verified_public_notices(classified)
    except Exception:
        logger.exception("telegram_pme_notify_failed")


def notify_robot_started() -> None:
    try:
        from app.application.services.telegram_events import (
            ROBOT_STARTED,
            format_robot_started,
        )

        dispatcher = get_telegram_dispatcher()
        if dispatcher is not None and dispatcher.enabled:
            dispatcher.forget("robot:stopped")
            status = "CONNECTED" if dispatcher.last_success else "ENABLED"
        else:
            status = "DISABLED"
        emit_telegram(
            ROBOT_STARTED,
            "robot:started",
            format_robot_started(telegram_status=status),
            telegram=False,
            jimvio=False,
        )
    except Exception:
        logger.exception("telegram_robot_started_failed")


def notify_robot_stopped(*, reason: str | None = None) -> None:
    try:
        from app.application.services.telegram_events import (
            ROBOT_STOPPED,
            format_robot_stopped,
        )

        dispatcher = get_telegram_dispatcher()
        if dispatcher is not None:
            dispatcher.forget("robot:started")
        emit_telegram(
            ROBOT_STOPPED,
            "robot:stopped",
            format_robot_stopped(reason=reason),
            telegram=False,
            jimvio=False,
        )
    except Exception:
        logger.exception("telegram_robot_stopped_failed")


def notify_system_error(*, reason: str | None) -> None:
    try:
        from app.application.services.telegram_events import (
            SYSTEM_ERROR,
            format_system_error,
        )

        emit_telegram(
            SYSTEM_ERROR,
            f"sys:{reason or 'error'}",
            format_system_error(reason=reason),
            telegram=False,
            jimvio=False,
        )
    except Exception:
        logger.exception("telegram_system_error_notify_failed")
