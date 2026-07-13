"""In-process lifecycle archive — no DB schema change."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.execution_intelligence.lifecycle import (
    ALLOWED_TRANSITIONS,
    LifecycleState,
)


@dataclass
class LifecycleEvent:
    state: LifecycleState
    at: str
    reason: str
    source: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleRecord:
    lifecycle_id: str
    request_id: str
    user_id: str
    symbol: str
    side: str
    order_type: str
    volume: str
    state: LifecycleState
    history: list[LifecycleEvent] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "lifecycle_id": self.lifecycle_id,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "volume": self.volume,
            "state": self.state.value,
            "history": [
                {
                    "state": e.state.value,
                    "at": e.at,
                    "reason": e.reason,
                    "source": e.source,
                    "meta": dict(e.meta),
                }
                for e in self.history
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived": self.archived,
        }


class LifecycleStore:
    """Process-scoped lifecycle registry (single-process shared store)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[str, LifecycleRecord] = {}
        self._by_request: dict[tuple[str, str], str] = {}

    def create(
        self,
        *,
        user_id: str,
        request_id: str,
        symbol: str,
        side: str,
        order_type: str,
        volume: str,
        initial: LifecycleState = LifecycleState.DRAFT,
        reason: str = "created",
        source: str = "execution_intelligence",
    ) -> LifecycleRecord:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            key = (user_id, request_id.strip())
            existing_id = self._by_request.get(key)
            if existing_id and existing_id in self._by_id:
                return self._by_id[existing_id]
            lid = str(uuid4())
            event = LifecycleEvent(
                state=initial, at=now, reason=reason, source=source
            )
            rec = LifecycleRecord(
                lifecycle_id=lid,
                request_id=request_id.strip(),
                user_id=user_id,
                symbol=symbol.upper(),
                side=side,
                order_type=order_type,
                volume=volume,
                state=initial,
                history=[event],
                created_at=now,
                updated_at=now,
            )
            self._by_id[lid] = rec
            self._by_request[key] = lid
            return rec

    def transition(
        self,
        *,
        user_id: str,
        request_id: str,
        to_state: LifecycleState,
        reason: str,
        source: str,
        meta: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            key = (user_id, request_id.strip())
            lid = self._by_request.get(key)
            if lid is None or lid not in self._by_id:
                return {
                    "ok": False,
                    "error": "Lifecycle not found — create/observe first",
                }
            rec = self._by_id[lid]
            if rec.state == to_state:
                return {"ok": True, "record": rec.to_dict(), "noop": True}
            allowed = ALLOWED_TRANSITIONS.get(rec.state, frozenset())
            if not force and to_state not in allowed:
                return {
                    "ok": False,
                    "error": (
                        f"Transition {rec.state.value} → {to_state.value} not allowed"
                    ),
                    "record": rec.to_dict(),
                }
            rec.history.append(
                LifecycleEvent(
                    state=to_state,
                    at=now,
                    reason=reason,
                    source=source,
                    meta=dict(meta or {}),
                )
            )
            rec.state = to_state
            rec.updated_at = now
            if to_state in {
                LifecycleState.CLOSED,
                LifecycleState.CANCELLED,
                LifecycleState.REJECTED,
            }:
                rec.archived = True
            return {"ok": True, "record": rec.to_dict()}

    def list_for_user(
        self, user_id: str, *, limit: int = 100, include_archived: bool = True
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = [r for r in self._by_id.values() if r.user_id == user_id]
            if not include_archived:
                rows = [r for r in rows if not r.archived]
            rows.sort(key=lambda r: r.updated_at, reverse=True)
            return [r.to_dict() for r in rows[:limit]]

    def get(self, user_id: str, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            lid = self._by_request.get((user_id, request_id.strip()))
            if not lid:
                return None
            rec = self._by_id.get(lid)
            return rec.to_dict() if rec else None
