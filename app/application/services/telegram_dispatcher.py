"""Non-blocking Telegram Bot API dispatcher.

Fail-open observability: enqueue never raises into trading code.
HTTP happens on an isolated asyncio task — not inside order_send, Risk,
OMS, PME policy, or signal scoring.
"""

from __future__ import annotations

import asyncio
import contextlib
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
from core.logging import get_logger

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org"
_MAX_QUEUE = 64
_MAX_SEEN = 2048
_SEEN_TTL_SECONDS = 6 * 3600
_TIMEOUT_SECONDS = 4.0
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)


class TelegramSender(Protocol):
    async def __call__(self, url: str, payload: dict[str, Any]) -> httpx.Response: ...


def _secret_text(value: Any) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    raw = getter() if callable(getter) else str(value)
    text = str(raw or "").strip()
    return text or None


def redact_secrets(text: str, *secrets: str | None) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def _safe_url_for_logs(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path
    if "/bot" in path:
        head, _sep, tail = path.partition("/bot")
        token_and_rest = tail
        slash = token_and_rest.find("/")
        rest = token_and_rest[slash:] if slash >= 0 else ""
        path = f"{head}/bot***/{rest.lstrip('/')}"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


@dataclass(frozen=True, slots=True)
class TelegramNotice:
    event: str
    event_id: str
    text: str


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
        if self._enabled and not (self._token and self._chat_id):
            self._enabled = False
            logger.warning(
                "telegram_disabled_missing_credentials",
                token_configured=bool(self._token),
                chat_id_configured=bool(self._chat_id),
            )

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

    def emit(self, event: str, event_id: str, text: str) -> None:
        """Enqueue a notice. Never raises. Never awaits Telegram HTTP."""
        try:
            if not self._enabled:
                return
            key = str(event_id or "").strip() or f"{event}:{time.time_ns()}"
            notice = TelegramNotice(event=str(event), event_id=key, text=str(text))
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
        payload = {
            "chat_id": self._chat_id,
            "text": notice.text,
            "disable_web_page_preview": True,
        }
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


def emit_telegram(event: str, event_id: str, text: str) -> None:
    """Process-wide fail-open emit. Safe to call from any trading observer."""
    try:
        dispatcher = get_telegram_dispatcher()
        if dispatcher is None:
            return
        dispatcher.emit(event, event_id, text)
    except Exception:
        logger.exception("telegram_emit_failed")


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
        dispatcher.emit_test()
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
                        )
                    else:
                        emit_telegram(
                            MT5_DISCONNECTED,
                            f"mt5:disconnected:{time.time_ns()}",
                            format_mt5_disconnected(),
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
                        )
                    else:
                        emit_telegram(
                            GATEWAY_OFFLINE,
                            f"gw:offline:{time.time_ns()}",
                            format_gateway_offline(),
                        )
    except Exception:
        logger.exception("telegram_connectivity_notify_failed")


def notify_cycle(
    cycle: Any,
    *,
    decision: Any = None,
    bridge: Any = None,
    pipeline: Any = None,
) -> None:
    try:
        from app.application.services.telegram_events import classify_cycle_notices

        for notice in classify_cycle_notices(
            cycle=cycle,
            decision=decision,
            bridge=bridge,
            pipeline=pipeline,
        ):
            emit_telegram(notice["event"], notice["event_id"], notice["text"])
    except Exception:
        logger.exception("telegram_cycle_notify_failed")


def notify_pme(result: Any, *, current_price: object = None) -> None:
    try:
        from app.application.services.telegram_events import classify_pme_notices

        for notice in classify_pme_notices(result=result, current_price=current_price):
            emit_telegram(notice["event"], notice["event_id"], notice["text"])
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
        )
    except Exception:
        logger.exception("telegram_system_error_notify_failed")
