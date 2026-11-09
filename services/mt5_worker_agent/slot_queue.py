"""Simple FIFO queue when the existing Windows host is at portable capacity.

Never starts a portable session that would exceed measured capacity.
Never attaches to the LIVE Weltrade Program Files terminal.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from services.mt5_worker_agent.host_capacity import can_start_another_portable


@dataclass(slots=True)
class QueueItem:
    broker_slug: str
    environment: str
    slot_preference: str
    requested_at: str = field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0).isoformat()
    )
    reason: str = "capacity_wait"


_LOCK = threading.Lock()
_QUEUE: list[QueueItem] = []


def _queue_path() -> Path:
    root = Path(os_environ_slot_root())
    return root / "_queue" / "pending.json"


def os_environ_slot_root() -> str:
    import os

    return (
        os.environ.get("QF_MT5_SLOT_ROOT") or r"C:\QuantForg-Workspace\mt5_worker_slots"
    )


def enqueue(
    *,
    broker_slug: str,
    environment: str = "demo",
    slot_preference: str = "demo-a",
) -> dict[str, Any]:
    item = QueueItem(
        broker_slug=broker_slug.strip().lower(),
        environment=environment.strip().lower() or "demo",
        slot_preference=slot_preference.strip() or "demo-a",
    )
    with _LOCK:
        _QUEUE.append(item)
        _persist()
        position = len(_QUEUE)
    return {
        "ok": True,
        "queued": True,
        "position": position,
        "item": asdict(item),
        "password_included": False,
    }


def dequeue_if_capacity() -> dict[str, Any] | None:
    ok, reason = can_start_another_portable()
    if not ok:
        return {"ok": False, "queued": True, "reason": reason, "item": None}
    with _LOCK:
        if not _QUEUE:
            return {"ok": True, "queued": False, "item": None, "reason": "queue_empty"}
        item = _QUEUE.pop(0)
        _persist()
    return {
        "ok": True,
        "queued": False,
        "item": asdict(item),
        "reason": "dequeued",
        "password_included": False,
    }


def snapshot() -> dict[str, Any]:
    with _LOCK:
        items = [asdict(i) for i in _QUEUE]
    return {
        "depth": len(items),
        "items": items,
        "password_included": False,
    }


def _persist() -> None:
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": [asdict(i) for i in _QUEUE]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_persisted() -> int:
    path = _queue_path()
    if not path.is_file():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("items") if isinstance(raw, dict) else None
        if not isinstance(items, list):
            return 0
        loaded: list[QueueItem] = []
        for row in items:
            if not isinstance(row, dict):
                continue
            loaded.append(
                QueueItem(
                    broker_slug=str(row.get("broker_slug") or ""),
                    environment=str(row.get("environment") or "demo"),
                    slot_preference=str(row.get("slot_preference") or "demo-a"),
                    requested_at=str(row.get("requested_at") or ""),
                    reason=str(row.get("reason") or "capacity_wait"),
                )
            )
        with _LOCK:
            _QUEUE.clear()
            _QUEUE.extend(loaded)
        return len(loaded)
    except Exception:
        return 0
