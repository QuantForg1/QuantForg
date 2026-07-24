"""Diagnostics — explain every reject and every take."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScalpingDiagnosticsStore:
    _events: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "ai_scalping_diagnostics_v5.jsonl"

    def record(
        self,
        *,
        outcome: str,
        symbol: str,
        direction: str | None,
        confidence: int | None,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ev = {
            "id": str(uuid4()),
            "at": datetime.now(UTC).isoformat(),
            "outcome": outcome,  # rejected | taken
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "reason": reason,
            "details": details or {},
        }
        with self._lock:
            self._events.append(ev)
            self._events = self._events[-2000:]
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev, default=str) + "\n")
        except Exception:
            logger.exception("scalping_diagnostics_persist_failed")
        return ev

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._events[-max(1, limit) :]))

    def summary(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._events)
        rejected = sum(1 for r in rows if r.get("outcome") == "rejected")
        taken = sum(1 for r in rows if r.get("outcome") == "taken")
        return {"total": len(rows), "rejected": rejected, "taken": taken}


_STORE: ScalpingDiagnosticsStore | None = None
_LOCK = threading.Lock()


def get_scalping_diagnostics_store() -> ScalpingDiagnosticsStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ScalpingDiagnosticsStore()
        return _STORE
