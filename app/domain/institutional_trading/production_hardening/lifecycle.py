"""Execution lifecycle timeline — every stage timestamped, no silent failures."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.production_hardening.config import (
    DEFAULT_HARDENING_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)

LIFECYCLE_STAGES: tuple[str, ...] = (
    "SIGNAL",
    "AI_DECISION",
    "RISK_VALIDATION",
    "OMS",
    "MT5_GATEWAY",
    "BROKER",
    "CONFIRMATION",
    "POSITION_MONITOR",
    "EXIT",
)


@dataclass
class LifecycleEvent:
    trace_id: str
    stage: str
    status: str  # started | ok | failed | skipped
    detail: str
    at: str
    latency_ms: float | None = None
    symbol: str | None = None
    ticket: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionLifecycleStore:
    max_events: int = DEFAULT_HARDENING_CONFIG.lifecycle_max_events
    _events: list[LifecycleEvent] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "execution_lifecycle.jsonl"

    def record(
        self,
        *,
        stage: str,
        status: str,
        detail: str,
        trace_id: str | None = None,
        latency_ms: float | None = None,
        symbol: str | None = None,
        ticket: str | None = None,
    ) -> LifecycleEvent:
        stage_u = stage.upper()
        if stage_u not in LIFECYCLE_STAGES and stage_u not in {
            "RETRY",
            "RECOVERY",
            "INCIDENT",
        }:
            stage_u = stage
        ev = LifecycleEvent(
            trace_id=trace_id or str(uuid4()),
            stage=stage_u,
            status=status,
            detail=detail[:500],
            at=datetime.now(UTC).isoformat(),
            latency_ms=round(latency_ms, 3) if latency_ms is not None else None,
            symbol=symbol,
            ticket=str(ticket) if ticket is not None else None,
        )
        with self._lock:
            self._events.append(ev)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events :]
        logger.info(
            "execution_lifecycle",
            stage=ev.stage,
            status=ev.status,
            detail=ev.detail,
            trace_id=ev.trace_id,
            latency_ms=ev.latency_ms,
            symbol=ev.symbol,
            ticket=ev.ticket,
        )
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev.to_dict()) + "\n")
        except Exception:
            logger.exception("execution_lifecycle_persist_failed")
        return ev

    def recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._events[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]

    def for_trace(self, trace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = [e for e in self._events if e.trace_id == trace_id]
        return [r.to_dict() for r in rows]


_STORE: ExecutionLifecycleStore | None = None
_LOCK = threading.Lock()


def get_lifecycle_store() -> ExecutionLifecycleStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ExecutionLifecycleStore()
        return _STORE
