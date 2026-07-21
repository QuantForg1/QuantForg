"""Auditable operator notes for Mission Control."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class OperatorNote:
    note_id: str
    operator: str
    text: str
    created_at: str
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "operator": self.operator,
            "text": self.text,
            "created_at": self.created_at,
            "tags": list(self.tags),
        }


@dataclass
class OperatorNotesStore:
    max_notes: int = 200
    _items: list[OperatorNote] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def add(
        self,
        text: str,
        *,
        operator: str = "operator",
        tags: list[str] | None = None,
    ) -> OperatorNote:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("note text required")
        note = OperatorNote(
            note_id=f"mcn_{uuid4().hex[:12]}",
            operator=operator.strip() or "operator",
            text=cleaned[:4000],
            created_at=datetime.now(UTC).isoformat(),
            tags=tuple(t.strip() for t in (tags or []) if t.strip())[:8],
        )
        with self._lock:
            self._items.insert(0, note)
            if len(self._items) > self.max_notes:
                self._items = self._items[: self.max_notes]
        return note

    def list(self, *, limit: int = 50) -> list[OperatorNote]:
        with self._lock:
            return list(self._items[: max(1, min(limit, self.max_notes))])

    def search(self, query: str, *, limit: int = 20) -> list[OperatorNote]:
        q = query.strip().lower()
        if not q:
            return []
        with self._lock:
            hits = [
                n
                for n in self._items
                if q in n.text.lower()
                or q in n.operator.lower()
                or any(q in t.lower() for t in n.tags)
            ]
        return hits[: max(1, min(limit, 50))]
