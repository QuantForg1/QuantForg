"""QEM immutable event store under data/qem/ — never production tables."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qem" / "workspace.json"


class QemStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._events: list[dict[str, Any]] = []
        self._event_ids: set[str] = set()
        self._subscribers: list[dict[str, Any]] = []
        self._snapshot: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._events = list(raw.get("events") or [])
        self._event_ids = {
            str(e.get("id")) for e in self._events if isinstance(e, dict) and e.get("id")
        }
        self._subscribers = list(raw.get("subscribers") or [])
        self._snapshot = dict(raw.get("snapshot") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "qem_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "events_immutable": True,
                "events": self._events[-2000:],
                "subscribers": self._subscribers,
                "snapshot": self._snapshot,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def append_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Append-only. Duplicate IDs are rejected (immutability)."""
        eid = str(event.get("id") or uuid4())
        with self._lock:
            if eid in self._event_ids:
                return None
            row = {
                **event,
                "id": eid,
                "immutable": True,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
            self._events.append(row)
            self._event_ids.add(eid)
            if len(self._events) > 2500:
                dropped = self._events[:-2000]
                self._events = self._events[-2000:]
                for d in dropped:
                    self._event_ids.discard(str(d.get("id")))
            self._persist()
            return deepcopy(row)

    def list_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(e) for e in self._events[-limit:]]

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            for e in reversed(self._events):
                if str(e.get("id")) == event_id:
                    return deepcopy(e)
            return None

    def set_subscribers(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            self._subscribers = [deepcopy(r) for r in rows]
            self._persist()
            return deepcopy(self._subscribers)

    def list_subscribers(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._subscribers)

    def save_snapshot(self, snap: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._snapshot = {
                "stats": snap.get("stats"),
                "observed_at": snap.get("observed_at") or datetime.now(UTC).isoformat(),
                "elapsed_ms": snap.get("elapsed_ms"),
            }
            self._persist()
            return deepcopy(self._snapshot)

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot)
