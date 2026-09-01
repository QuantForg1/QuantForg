"""Fail-open Jimvio webhook publisher.

Fan-out from the existing Telegram event path. HMAC-SHA256 signs the exact
JSON bytes posted. Delivery never awaits inside Risk, OMS, order_send, PME,
scoring, or the ITE loop. Telegram remains an independent target.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any, Protocol

import httpx

from app.application.services.telegram_events import (
    BREAKEVEN_SET,
    GATEWAY_OFFLINE,
    GATEWAY_ONLINE,
    MT5_CONNECTED,
    MT5_DISCONNECTED,
    OMS_REJECTED,
    ORDER_EXECUTION_ERROR,
    PARTIAL_CLOSE,
    RISK_BLOCKED,
    ROBOT_STARTED,
    ROBOT_STOPPED,
    SIGNAL_CONFIRMED,
    SIGNAL_GENERATED,
    SL_CREATED,
    SL_UPDATED,
    STOP_LOSS,
    SYSTEM_ERROR,
    TAKE_PROFIT,
    TELEGRAM_TEST,
    TP_CREATED,
    TP_UPDATED,
    TRADE_CLOSED,
    TRADE_OPENED,
    TRADE_REJECTED,
    TRAILING_STOP_UPDATED,
)
from core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_JIMVIO_WEBHOOK_URL = "https://www.jimvio.com/api/webhooks/quantforg"
SIGNATURE_HEADER = "X-QuantForg-Signature"
_MAX_QUEUE = 64
_MAX_SEEN = 2048
_SEEN_TTL_SECONDS = 6 * 3600
_TIMEOUT_SECONDS = 4.0
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (0.5, 1.0, 2.0)

JIMVIO_EVENT_TYPE = {
    SIGNAL_GENERATED: "SIGNAL_DETECTED",
    SIGNAL_CONFIRMED: "SIGNAL_CONFIRMED",
    TRADE_OPENED: "TRADE_OPENED",
    TRADE_REJECTED: "TRADE_REJECTED",
    SL_CREATED: "STOP_LOSS_SET",
    SL_UPDATED: "STOP_LOSS_SET",
    TP_CREATED: "TAKE_PROFIT_SET",
    TP_UPDATED: "TAKE_PROFIT_SET",
    BREAKEVEN_SET: "BREAKEVEN_SET",
    TRAILING_STOP_UPDATED: "TRAILING_STOP_UPDATED",
    PARTIAL_CLOSE: "PARTIAL_CLOSE",
    TAKE_PROFIT: "TAKE_PROFIT_HIT",
    STOP_LOSS: "STOP_LOSS_HIT",
    TRADE_CLOSED: "TRADE_CLOSED",
    RISK_BLOCKED: "RISK_REJECTED",
    OMS_REJECTED: "TRADE_REJECTED",
    ORDER_EXECUTION_ERROR: "SYSTEM_ERROR",
    ROBOT_STARTED: "ROBOT_STARTED",
    ROBOT_STOPPED: "ROBOT_STOPPED",
    MT5_CONNECTED: "MT5_CONNECTED",
    MT5_DISCONNECTED: "MT5_DISCONNECTED",
    SYSTEM_ERROR: "SYSTEM_ERROR",
    GATEWAY_ONLINE: "SYSTEM_ERROR",
    GATEWAY_OFFLINE: "SYSTEM_ERROR",
}

JIMVIO_STATUS = {
    "SIGNAL_DETECTED": "DETECTED",
    "SIGNAL_CONFIRMED": "CONFIRMED",
    "TRADE_OPENED": "EXECUTED",
    "TRADE_REJECTED": "REJECTED",
    "STOP_LOSS_SET": "UPDATED",
    "TAKE_PROFIT_SET": "UPDATED",
    "BREAKEVEN_SET": "UPDATED",
    "TRAILING_STOP_UPDATED": "UPDATED",
    "PARTIAL_CLOSE": "UPDATED",
    "TAKE_PROFIT_HIT": "CLOSED",
    "STOP_LOSS_HIT": "CLOSED",
    "TRADE_CLOSED": "CLOSED",
    "RISK_REJECTED": "REJECTED",
    "ROBOT_STARTED": "RUNNING",
    "ROBOT_STOPPED": "STOPPED",
    "MT5_CONNECTED": "CONNECTED",
    "MT5_DISCONNECTED": "DISCONNECTED",
    "SYSTEM_ERROR": "ERROR",
}

_SKIP_EVENTS = frozenset({TELEGRAM_TEST})


class JimvioSender(Protocol):
    async def __call__(
        self, url: str, headers: dict[str, str], body: bytes
    ) -> httpx.Response: ...


def _secret_text(value: Any) -> str | None:
    if value is None:
        return None
    getter = getattr(value, "get_secret_value", None)
    raw = getter() if callable(getter) else str(value)
    text = str(raw or "").strip()
    return text or None


def _json_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError, TypeError):
        return None


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def serialize_jimvio_body(payload: dict[str, Any]) -> bytes:
    """Compact JSON bytes that must match the POST body exactly."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def jimvio_signature(body: bytes, secret: str) -> str:
    """HMAC-SHA256 hex digest of the raw request body."""
    key = str(secret or "").encode("utf-8")
    if not key:
        raise ValueError("missing_webhook_secret")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def map_jimvio_event_type(quantforg_event: str) -> str | None:
    event = str(quantforg_event or "").strip()
    if event in _SKIP_EVENTS:
        return None
    if event in JIMVIO_EVENT_TYPE:
        return JIMVIO_EVENT_TYPE[event]
    return None


def build_jimvio_payload(
    *,
    event: str,
    event_id: str,
    message: str | None = None,
    fields: dict[str, Any] | None = None,
    timestamp: str | None = None,
    status_override: str | None = None,
) -> dict[str, Any] | None:
    event_type = map_jimvio_event_type(event)
    if event_type is None:
        return None
    key = str(event_id or "").strip()
    if not key:
        return None
    extra = dict(fields or {})
    ticket = extra.get("ticket") or extra.get("mt5_ticket")
    if event_type == "TRADE_OPENED" and ticket in (None, "", 0, "0"):
        event_type = "TRADE_REJECTED"
    status = str(status_override or "").strip() or JIMVIO_STATUS.get(
        event_type, "UPDATED"
    )
    payload: dict[str, Any] = {
        "event_id": key,
        "event_type": event_type,
        "timestamp": timestamp or utc_now_iso(),
        "status": status,
    }
    symbol = extra.get("symbol")
    if symbol:
        payload["symbol"] = str(symbol).upper()
    direction = extra.get("direction") or extra.get("side")
    if direction:
        payload["direction"] = str(direction).upper()
    for src, dest in (
        ("entry", "entry"),
        ("stop_loss", "stop_loss"),
        ("take_profit", "take_profit"),
        ("current_price", "current_price"),
    ):
        number = _json_number(extra.get(src))
        if number is not None:
            payload[dest] = number
    text = str(message or "").strip()
    if text:
        payload["message"] = text
    metadata: dict[str, Any] = {"quantforg_event": str(event)}
    if ticket not in (None, "", 0, "0"):
        metadata["mt5_ticket"] = ticket
    for meta_key in ("reason", "test", "volume", "retcode"):
        if extra.get(meta_key) not in (None, ""):
            metadata[meta_key] = extra[meta_key]
    payload["metadata"] = metadata
    return payload


def build_test_payload(
    *, event_id: str = "quantforg-integration-test-001"
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": "SYSTEM_ERROR",
        "timestamp": utc_now_iso(),
        "status": "TEST",
        "message": "QuantForg → Jimvio integration test",
        "metadata": {"test": True},
    }


def signed_request(payload: dict[str, Any], secret: str) -> tuple[bytes, str]:
    body = serialize_jimvio_body(payload)
    return body, jimvio_signature(body, secret)


@dataclass(frozen=True, slots=True)
class JimvioNotice:
    event: str
    event_id: str
    payload: dict[str, Any]


class JimvioPublisher:
    """Bounded in-memory queue + isolated HTTP worker."""

    def __init__(
        self,
        *,
        enabled: bool,
        webhook_url: str | None = None,
        secret: Any = None,
        sender: JimvioSender | None = None,
        timeout_seconds: float = _TIMEOUT_SECONDS,
        max_attempts: int = _MAX_ATTEMPTS,
    ) -> None:
        self._enabled = bool(enabled)
        self._url = str(webhook_url or DEFAULT_JIMVIO_WEBHOOK_URL).strip()
        self._secret = _secret_text(secret)
        self._sender = sender
        self._timeout = float(timeout_seconds)
        self._max_attempts = max(1, int(max_attempts))
        self._queue: deque[JimvioNotice] = deque()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._lock = Lock()
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._last_success = False
        if self._enabled and not (self._secret and self._url.startswith("https://")):
            self._enabled = False
            logger.warning(
                "jimvio_disabled_missing_credentials",
                secret_configured=bool(self._secret),
                url_configured=bool(self._url),
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

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
        message: str | None = None,
        *,
        fields: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue a signed webhook. Never raises. Never awaits HTTP."""
        try:
            if not self._enabled:
                return
            body = payload or build_jimvio_payload(
                event=event,
                event_id=event_id,
                message=message,
                fields=fields,
            )
            if not body:
                return
            key = str(body.get("event_id") or event_id or "").strip()
            notice = JimvioNotice(event=str(event), event_id=key, payload=body)
            with self._lock:
                if self._already_seen(key):
                    logger.info(
                        "jimvio_duplicate_suppressed",
                        jimvio_event=notice.event,
                        event_id=key,
                    )
                    return
                self._mark_seen(key)
                if len(self._queue) >= _MAX_QUEUE:
                    dropped = self._queue.popleft()
                    logger.warning(
                        "jimvio_queue_overflow_drop",
                        dropped_event=dropped.event,
                        jimvio_event=notice.event,
                    )
                self._queue.append(notice)
        except Exception:
            logger.exception("jimvio_emit_failed")

    def emit_test(self, *, event_id: str = "quantforg-integration-test-001") -> None:
        self.emit(
            SYSTEM_ERROR,
            event_id,
            payload=build_test_payload(event_id=event_id),
        )

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
        self._task = loop.create_task(self._worker(), name="jimvio-publisher")

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def flush(self, *, wait_seconds: float = 3.0) -> None:
        try:
            deadline = time.monotonic() + max(0.05, float(wait_seconds))
            while time.monotonic() < deadline:
                with self._lock:
                    notice = self._queue.popleft() if self._queue else None
                    empty = notice is None
                if notice is None:
                    if empty:
                        return
                    continue
                await self._deliver(notice)
        except Exception:
            logger.exception("jimvio_flush_failed")

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
            notice: JimvioNotice | None = None
            with self._lock:
                if self._queue:
                    notice = self._queue.popleft()
            if notice is None:
                await asyncio.sleep(0.05)
                continue
            await self._deliver(notice)

    async def _deliver(self, notice: JimvioNotice) -> None:
        try:
            await self._send_with_retry(notice)
        except Exception as exc:
            self._last_success = False
            logger.warning(
                "jimvio_notification_failed",
                jimvio_event=notice.event,
                event_id=notice.event_id,
                error=type(exc).__name__,
            )

    async def _send_with_retry(self, notice: JimvioNotice) -> None:
        if not self._secret or not self._url:
            return
        body, signature = signed_request(notice.payload, self._secret)
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: signature,
        }
        last_error = "unknown"
        logger.info(
            "jimvio_webhook_request_started",
            jimvio_event=notice.event,
            event_id=notice.event_id,
        )
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._post(self._url, headers, body)
            except httpx.TimeoutException as exc:
                last_error = type(exc).__name__
                logger.warning(
                    "jimvio_webhook_timeout",
                    jimvio_event=notice.event,
                    event_id=notice.event_id,
                    attempt=attempt,
                )
                if attempt >= self._max_attempts:
                    break
                logger.info(
                    "jimvio_webhook_retry",
                    jimvio_event=notice.event,
                    event_id=notice.event_id,
                    attempt=attempt,
                )
                await asyncio.sleep(
                    _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
                )
                continue
            except (httpx.NetworkError, OSError) as exc:
                last_error = type(exc).__name__
                if attempt >= self._max_attempts:
                    break
                logger.info(
                    "jimvio_webhook_retry",
                    jimvio_event=notice.event,
                    event_id=notice.event_id,
                    attempt=attempt,
                    error=last_error,
                )
                await asyncio.sleep(
                    _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
                )
                continue
            except Exception as exc:
                last_error = type(exc).__name__
                break
            status = int(getattr(response, "status_code", 0) or 0)
            logger.info(
                "jimvio_webhook_response",
                jimvio_event=notice.event,
                event_id=notice.event_id,
                status=status,
            )
            if 200 <= status < 300:
                self._last_success = True
                logger.info(
                    "jimvio_notification_sent",
                    jimvio_event=notice.event,
                    event_id=notice.event_id,
                    status=status,
                )
                return
            last_error = f"http_{status}"
            retryable = status == 429 or status >= 500
            if not retryable or attempt >= self._max_attempts:
                logger.warning(
                    "jimvio_webhook_failed",
                    jimvio_event=notice.event,
                    event_id=notice.event_id,
                    status=status,
                )
                logger.warning(
                    "jimvio_notification_failed",
                    jimvio_event=notice.event,
                    event_id=notice.event_id,
                    status=status,
                )
                self._last_success = False
                return
            logger.info(
                "jimvio_webhook_retry",
                jimvio_event=notice.event,
                event_id=notice.event_id,
                attempt=attempt,
                status=status,
            )
            wait = _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
            await asyncio.sleep(wait)
        self._last_success = False
        logger.warning(
            "jimvio_webhook_failed",
            jimvio_event=notice.event,
            event_id=notice.event_id,
            error=last_error,
        )
        logger.warning(
            "jimvio_notification_failed",
            jimvio_event=notice.event,
            event_id=notice.event_id,
            error=last_error,
        )

    async def _post(
        self, url: str, headers: dict[str, str], body: bytes
    ) -> httpx.Response:
        if self._sender is not None:
            return await self._sender(url, headers, body)
        timeout = httpx.Timeout(self._timeout, connect=self._timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, content=body, headers=headers)


_publisher: JimvioPublisher | None = None
_publisher_lock = Lock()


def get_jimvio_publisher() -> JimvioPublisher | None:
    return _publisher


def reset_jimvio_publisher_for_tests(
    publisher: JimvioPublisher | None = None,
) -> JimvioPublisher | None:
    global _publisher
    with _publisher_lock:
        _publisher = publisher
    return _publisher


def emit_jimvio(
    event: str,
    event_id: str,
    message: str | None = None,
    *,
    fields: dict[str, Any] | None = None,
) -> None:
    """Process-wide fail-open emit. Safe from any trading observer."""
    try:
        publisher = get_jimvio_publisher()
        if publisher is None:
            return
        publisher.emit(event, event_id, message, fields=fields)
    except Exception:
        logger.exception("jimvio_emit_failed")


def _settings_webhook_secret(settings: Any) -> Any:
    primary = getattr(settings, "quantforg_webhook_secret", None)
    if _secret_text(primary):
        return primary
    fallback = (
        os.environ.get("QUANTFORG_WEBHOOK_SECRET")
        or os.environ.get("JIMVIO_WEBHOOK_SECRET")
        or ""
    ).strip()
    return fallback or None


async def start_jimvio_publisher(settings: Any) -> JimvioPublisher:
    global _publisher
    publisher = JimvioPublisher(
        enabled=bool(getattr(settings, "jimvio_enabled", False)),
        webhook_url=getattr(settings, "jimvio_webhook_url", None)
        or DEFAULT_JIMVIO_WEBHOOK_URL,
        secret=_settings_webhook_secret(settings),
    )
    with _publisher_lock:
        previous = _publisher
        _publisher = publisher
    if previous is not None:
        await previous.stop()
    publisher.start()
    if publisher.enabled:
        logger.info("jimvio_publisher_started", enabled=True)
    else:
        logger.info("jimvio_publisher_disabled")
    return publisher


async def stop_jimvio_publisher() -> None:
    global _publisher
    with _publisher_lock:
        publisher = _publisher
        _publisher = None
    if publisher is not None:
        await publisher.stop()
