"""Component heartbeats — missing beat → incident."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.domain.institutional_trading.reliability.models import (
    ComponentName,
    Heartbeat,
)


@dataclass
class HeartbeatRegistry:
    """Every component publishes heartbeat; stale → missing list."""

    timeout_seconds: float = 30.0
    _beats: dict[ComponentName, Heartbeat] = field(default_factory=dict, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def publish(
        self,
        component: ComponentName,
        *,
        latency_ms: float = 0.0,
        now: datetime | None = None,
        meta: dict | None = None,
    ) -> Heartbeat:
        hb = Heartbeat(
            component=component,
            at=now or datetime.now(UTC),
            latency_ms=latency_ms,
            meta=dict(meta or {}),
        )
        with self._lock:
            self._beats[component] = hb
        return hb

    def last(self, component: ComponentName) -> Heartbeat | None:
        with self._lock:
            return self._beats.get(component)

    def missing(
        self,
        required: tuple[ComponentName, ...] | None = None,
        *,
        now: datetime | None = None,
    ) -> list[ComponentName]:
        moment = now or datetime.now(UTC)
        comps = required or tuple(ComponentName)
        out: list[ComponentName] = []
        with self._lock:
            for c in comps:
                hb = self._beats.get(c)
                if hb is None:
                    out.append(c)
                    continue
                age = (moment - hb.at).total_seconds()
                if age > self.timeout_seconds:
                    out.append(c)
        return out

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "timeout_seconds": self.timeout_seconds,
                "beats": {k.value: v.to_dict() for k, v in self._beats.items()},
            }
