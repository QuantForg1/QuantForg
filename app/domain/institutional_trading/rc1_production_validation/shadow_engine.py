"""Shadow trading logger — build + record broker payloads; never send."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ShadowTradingJournal:
    """Records exact order payloads and expected broker requests."""

    def __init__(self, *, max_entries: int = 2000) -> None:
        self._lock = Lock()
        self._max = max(50, int(max_entries))
        self._entries: list[dict[str, Any]] = []

    def record(
        self,
        *,
        order_payload: dict[str, Any],
        broker_request: dict[str, Any] | None = None,
        broker_response: dict[str, Any] | None = None,
        expected_execution: dict[str, Any] | None = None,
        symbol: str = "",
        decision_id: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "shadow_id": f"shd_{uuid4().hex[:12]}",
            "timestamp": _now_iso(),
            "symbol": symbol,
            "decision_id": decision_id,
            "order_payload": dict(order_payload or {}),
            "broker_request": dict(broker_request or {}),
            "broker_response": dict(broker_response or {"status": "not_sent"}),
            "expected_execution": dict(
                expected_execution
                or {
                    "would_submit": True,
                    "submitted": False,
                    "mode": "shadow",
                }
            ),
            "submitted": False,
            "mt5_called": False,
        }
        with self._lock:
            self._entries.append(entry)
            while len(self._entries) > self._max:
                self._entries.pop(0)
        return entry

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._entries))[: max(1, min(limit, 200))]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "shadow_orders_recorded": len(self._entries),
                "broker_submissions": 0,
                "mt5_calls": 0,
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_JOURNAL: ShadowTradingJournal | None = None
_JOURNAL_LOCK = Lock()


def get_shadow_journal() -> ShadowTradingJournal:
    global _JOURNAL
    with _JOURNAL_LOCK:
        if _JOURNAL is None:
            _JOURNAL = ShadowTradingJournal()
        return _JOURNAL


def reset_shadow_journal_for_tests() -> ShadowTradingJournal:
    global _JOURNAL
    with _JOURNAL_LOCK:
        _JOURNAL = ShadowTradingJournal()
        return _JOURNAL
