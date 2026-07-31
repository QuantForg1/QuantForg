"""In-memory trade journal — stores every eligible / rejected validation trade."""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.domain.institutional_trading.rc1_production_validation.trade_record import (
    TradeRecord,
)


class TradeRecorder:
    """Thread-safe store for RC1 trade evidence."""

    def __init__(self, *, max_records: int = 5000) -> None:
        self._lock = Lock()
        self._max = max(100, int(max_records))
        self._records: dict[str, TradeRecord] = {}
        self._order: list[str] = []

    def record(self, trade: TradeRecord) -> TradeRecord:
        with self._lock:
            self._records[trade.trade_id] = trade
            self._order.append(trade.trade_id)
            while len(self._order) > self._max:
                old = self._order.pop(0)
                self._records.pop(old, None)
        return trade

    def get(self, trade_id: str) -> TradeRecord | None:
        with self._lock:
            return self._records.get(trade_id)

    def all(self) -> list[TradeRecord]:
        with self._lock:
            return [self._records[i] for i in self._order if i in self._records]

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(reversed(self._order))[: max(1, min(limit, 500))]
            return [self._records[i].to_dict() for i in ids if i in self._records]

    def stats(self) -> dict[str, Any]:
        rows = self.all()
        accepted = [r for r in rows if r.accepted]
        rejected = [r for r in rows if not r.accepted]
        qualities = [r.quality for r in accepted if r.quality is not None]
        confidences = [r.confidence for r in accepted if r.confidence is not None]
        return {
            "total": len(rows),
            "eligible": len(accepted),
            "rejected": len(rejected),
            "accepted_quality_avg": (
                round(sum(qualities) / len(qualities), 2) if qualities else None
            ),
            "accepted_confidence_avg": (
                round(sum(confidences) / len(confidences), 2) if confidences else None
            ),
        }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._order.clear()


_RECORDER: TradeRecorder | None = None
_RECORDER_LOCK = Lock()


def get_trade_recorder() -> TradeRecorder:
    global _RECORDER
    with _RECORDER_LOCK:
        if _RECORDER is None:
            _RECORDER = TradeRecorder()
        return _RECORDER


def reset_trade_recorder_for_tests() -> TradeRecorder:
    global _RECORDER
    with _RECORDER_LOCK:
        _RECORDER = TradeRecorder()
        return _RECORDER
