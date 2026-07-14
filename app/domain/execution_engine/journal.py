"""In-process execution journal — no DB schema change."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass
class ExecutionJournalEntry:
    """Observable blotter row for a single pipeline run / OMS action."""

    journal_id: str
    timestamp: str
    user_id: str
    request_id: str
    latency_ms: float | None
    gateway: str
    broker: str
    order_id: str | None
    ticket: int | None
    volume: str
    price: str
    slippage: str | None
    commission: str | None
    swap: str | None
    reason: str
    execution_result: str
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    action: str = "submit"
    stages: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_id": self.journal_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
            "gateway": self.gateway,
            "broker": self.broker,
            "order_id": self.order_id,
            "ticket": self.ticket,
            "volume": self.volume,
            "price": self.price,
            "slippage": self.slippage,
            "commission": self.commission,
            "swap": self.swap,
            "reason": self.reason,
            "execution_result": self.execution_result,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "action": self.action,
            "stages": list(self.stages),
            "meta": dict(self.meta),
        }


class ExecutionJournalStore:
    """Process-scoped journal (shared across requests in one worker)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: list[ExecutionJournalEntry] = []

    def append(self, entry: ExecutionJournalEntry) -> ExecutionJournalEntry:
        with self._lock:
            self._entries.append(entry)
            # Cap memory — keep newest 2k
            if len(self._entries) > 2000:
                self._entries = self._entries[-2000:]
            return entry

    def record(
        self,
        *,
        user_id: str,
        request_id: str,
        latency_ms: float | None,
        gateway: str,
        broker: str,
        order_id: str | None,
        ticket: int | None,
        volume: str,
        price: str,
        slippage: str | None,
        commission: str | None,
        swap: str | None,
        reason: str,
        execution_result: str,
        symbol: str = "",
        side: str = "",
        order_type: str = "",
        action: str = "submit",
        stages: list[dict[str, Any]] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = ExecutionJournalEntry(
            journal_id=str(uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            user_id=user_id,
            request_id=request_id,
            latency_ms=latency_ms,
            gateway=gateway,
            broker=broker,
            order_id=order_id,
            ticket=ticket,
            volume=volume,
            price=price,
            slippage=slippage,
            commission=commission,
            swap=swap,
            reason=reason,
            execution_result=execution_result,
            symbol=symbol,
            side=side,
            order_type=order_type,
            action=action,
            stages=list(stages or []),
            meta=dict(meta or {}),
        )
        return self.append(entry).to_dict()

    def list_for_user(self, user_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = [e for e in self._entries if e.user_id == user_id]
            rows.reverse()
            return [e.to_dict() for e in rows[:limit]]

    def all_recent(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(reversed(self._entries[-limit:]))
            return [e.to_dict() for e in rows]
