"""Permanent audit trail for config / risk / weight / mode changes."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.research_platform.config import (
    DEFAULT_RESEARCH_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AuditEvent:
    id: str
    at: str
    user: str
    category: str
    key: str
    previous_value: Any
    new_value: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditTrailStore:
    _events: list[AuditEvent] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "research_audit_trail_v10.jsonl"

    def record(
        self,
        *,
        user: str,
        category: str,
        key: str,
        previous_value: Any,
        new_value: Any,
        reason: str,
    ) -> AuditEvent:
        # Never store secrets
        for token in ("password", "secret", "token", "api_key", "credential"):
            if token in key.lower() or token in str(category).lower():
                previous_value = "[redacted]"
                new_value = "[redacted]"
                break
        ev = AuditEvent(
            id=str(uuid4()),
            at=datetime.now(UTC).isoformat(),
            user=user,
            category=category,
            key=key,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
        )
        with self._lock:
            self._events.append(ev)
            if len(self._events) > DEFAULT_RESEARCH_CONFIG.max_audit_events:
                self._events = self._events[-DEFAULT_RESEARCH_CONFIG.max_audit_events :]
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev.to_dict(), default=str) + "\n")
        except Exception:
            logger.exception("audit_trail_persist_failed")
        logger.info(
            "audit_trail_event",
            user=user,
            category=category,
            key=key,
            reason=reason,
        )
        return ev

    def recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._events[-max(1, limit) :]
        return [e.to_dict() for e in reversed(rows)]


_STORE: AuditTrailStore | None = None
_LOCK = threading.Lock()


def get_audit_trail() -> AuditTrailStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = AuditTrailStore()
        return _STORE
