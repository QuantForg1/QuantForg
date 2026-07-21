"""Knowledge Base — auditable research notes; never invents content."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class KnowledgeEntry:
    entry_id: str
    title: str
    body: str
    author: str
    tags: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "body": self.body,
            "author": self.author,
            "tags": list(self.tags),
            "created_at": self.created_at,
        }


@dataclass
class KnowledgeBaseStore:
    max_entries: int = 200
    _items: list[KnowledgeEntry] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def add(
        self,
        *,
        title: str,
        body: str,
        author: str = "researcher",
        tags: list[str] | None = None,
    ) -> KnowledgeEntry:
        t = title.strip()
        b = body.strip()
        if not t or not b:
            raise ValueError("title and body required")
        entry = KnowledgeEntry(
            entry_id=f"kb_{uuid4().hex[:12]}",
            title=t[:200],
            body=b[:8000],
            author=(author.strip() or "researcher")[:120],
            tags=tuple(x.strip() for x in (tags or []) if x.strip())[:12],
            created_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            self._items.insert(0, entry)
            if len(self._items) > self.max_entries:
                self._items = self._items[: self.max_entries]
        return entry

    def list(self, *, limit: int = 50) -> list[KnowledgeEntry]:
        with self._lock:
            return list(self._items[: max(1, min(limit, self.max_entries))])

    def search(self, query: str, *, limit: int = 20) -> list[KnowledgeEntry]:
        q = query.strip().lower()
        if not q:
            return []
        with self._lock:
            hits = [
                e
                for e in self._items
                if q in e.title.lower()
                or q in e.body.lower()
                or q in e.author.lower()
                or any(q in t.lower() for t in e.tags)
            ]
        return hits[: max(1, min(limit, 50))]
