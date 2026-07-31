"""Trade lifecycle timeline — Signal → … → Archived for NOC."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

LIFECYCLE_STAGES: tuple[str, ...] = (
    "SIGNAL_DETECTED",
    "AI_APPROVED",
    "RISK_APPROVED",
    "PRE_APPROVED",
    "OMS_SUBMITTED",
    "BROKER_ACCEPTED",
    "FILLED",
    "MANAGED",
    "CLOSED",
    "ARCHIVED",
)

_LOCK = threading.Lock()
_STORE: "TradeLifecycleStore | None" = None


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class TradeLifecycleStore:
    window: int = 100
    _timelines: deque[dict[str, Any]] = field(default_factory=deque, repr=False)
    _active: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def begin(
        self,
        *,
        lifecycle_id: str,
        symbol: str,
        direction: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": lifecycle_id,
            "symbol": str(symbol or "").upper(),
            "direction": str(direction or "").upper() or None,
            "started_at": _iso(),
            "updated_at": _iso(),
            "current_stage": "SIGNAL_DETECTED",
            "stages": [
                {
                    "stage": "SIGNAL_DETECTED",
                    "at": _iso(),
                    "ok": True,
                    "reason": "signal",
                }
            ],
            "fabricated": False,
        }
        with self._lock:
            self._active[lifecycle_id] = row
        return dict(row)

    def mark(
        self,
        lifecycle_id: str,
        stage: str,
        *,
        ok: bool = True,
        reason: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        stage_u = str(stage or "").upper()
        if stage_u not in LIFECYCLE_STAGES:
            stage_u = stage_u or "SIGNAL_DETECTED"
        with self._lock:
            row = self._active.get(lifecycle_id)
            if row is None:
                row = {
                    "id": lifecycle_id,
                    "symbol": "",
                    "direction": None,
                    "started_at": _iso(),
                    "stages": [],
                    "fabricated": False,
                }
                self._active[lifecycle_id] = row
            row["updated_at"] = _iso()
            row["current_stage"] = stage_u
            entry = {
                "stage": stage_u,
                "at": _iso(),
                "ok": ok,
                "reason": reason,
                "metrics": dict(metrics or {}),
            }
            row["stages"].append(entry)
            if stage_u == "ARCHIVED":
                finished = dict(row)
                self._timelines.append(finished)
                while len(self._timelines) > self.window:
                    self._timelines.popleft()
                self._active.pop(lifecycle_id, None)
                return finished
            if stage_u == "CLOSED":
                # Keep active until ARCHIVED for NOC visibility of close reason
                return dict(row)
            return dict(row)

    def snapshot(self, *, limit: int = 20) -> dict[str, Any]:
        with self._lock:
            active = [dict(v) for v in self._active.values()]
            recent = list(reversed(list(self._timelines)[-limit:]))
        return {
            "stages_schema": list(LIFECYCLE_STAGES),
            "active": active,
            "recent": recent,
            "active_count": len(active),
            "recent_count": len(recent),
            "fabricated": False,
            "observe_only": True,
        }


def get_trade_lifecycle_store() -> TradeLifecycleStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = TradeLifecycleStore()
        return _STORE
