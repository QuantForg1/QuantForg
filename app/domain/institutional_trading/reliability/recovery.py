"""Automatic recovery — reconnect + safe reads only. Never retry order_send."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.domain.institutional_trading.reliability.models import (
    RecoveryAction,
    RecoveryEvent,
)

SafeReadFn = Callable[[], bool]
ReconnectFn = Callable[[], bool]


@dataclass
class RecoveryOrchestrator:
    """Recovery actions that are safe for production automation."""

    gateway_reconnect_fn: ReconnectFn | None = None
    mt5_reconnect_fn: ReconnectFn | None = None
    safe_read_fn: SafeReadFn | None = None
    max_safe_read_retries: int = 3
    max_events: int = 5_000
    _events: list[RecoveryEvent] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def recover_gateway(self, *, now: datetime | None = None) -> RecoveryEvent:
        ok = False
        detail = "no gateway_reconnect_fn configured"
        if self.gateway_reconnect_fn is not None:
            try:
                ok = bool(self.gateway_reconnect_fn())
                detail = "gateway reconnect attempted"
            except Exception as exc:
                ok = False
                detail = f"gateway reconnect failed: {exc}"
        return self._record(RecoveryAction.GATEWAY_RECONNECT, ok, detail, now=now)

    def recover_mt5(self, *, now: datetime | None = None) -> RecoveryEvent:
        ok = False
        detail = "no mt5_reconnect_fn configured"
        if self.mt5_reconnect_fn is not None:
            try:
                ok = bool(self.mt5_reconnect_fn())
                detail = "mt5 reconnect attempted"
            except Exception as exc:
                ok = False
                detail = f"mt5 reconnect failed: {exc}"
        return self._record(RecoveryAction.MT5_RECONNECT, ok, detail, now=now)

    def retry_safe_read(self, *, now: datetime | None = None) -> RecoveryEvent:
        """Retry idempotent reads only — never order_send."""
        if self.safe_read_fn is None:
            return self._record(
                RecoveryAction.SAFE_READ_RETRY,
                False,
                "no safe_read_fn configured",
                now=now,
            )
        last_err = ""
        for attempt in range(1, self.max_safe_read_retries + 1):
            try:
                if self.safe_read_fn():
                    return self._record(
                        RecoveryAction.SAFE_READ_RETRY,
                        True,
                        f"safe read ok on attempt {attempt}",
                        now=now,
                    )
                last_err = f"safe read returned false (attempt {attempt})"
            except Exception as exc:
                last_err = str(exc)
        return self._record(
            RecoveryAction.SAFE_READ_RETRY,
            False,
            f"safe read exhausted: {last_err}",
            now=now,
        )

    def retry_order_send(self) -> None:
        """Explicitly forbidden — automatic order_send retry is never allowed."""
        raise RuntimeError(
            "Automatic order_send retry is forbidden by Phase G recovery policy"
        )

    def _record(
        self,
        action: RecoveryAction,
        success: bool,
        detail: str,
        *,
        now: datetime | None,
    ) -> RecoveryEvent:
        ev = RecoveryEvent(
            action=action,
            success=success,
            detail=detail,
            at=now or datetime.now(UTC),
        )
        with self._lock:
            self._events.append(ev)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events :]
        return ev

    def list(self, *, limit: int = 100) -> list[RecoveryEvent]:
        with self._lock:
            return list(self._events[-limit:])
