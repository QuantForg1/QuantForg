"""Shared COP helpers — timestamps, redaction, paths."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

_SECRET_KEYS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|credential|private|"
    r"investor.?password|master.?password|auth)",
    re.I,
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_id(prefix: str = "cop") -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def data_path(filename: str) -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / "customer_operations" / filename


def redact(value: Any) -> Any:
    """Strip credentials and secrets from any nested structure."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _SECRET_KEYS.search(str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class JsonDocumentStore:
    """Thread-safe JSON document store (append-friendly collections)."""

    def __init__(self, filename: str, collection_key: str) -> None:
        self._path = data_path(filename)
        self._key = collection_key
        self._lock = threading.Lock()
        self._docs: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get(self._key, []) if isinstance(raw, dict) else []
            self._docs = [r for r in rows if isinstance(r, dict)]
        except Exception:
            self._docs = []

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": utc_iso(),
            self._key: list(self._docs),
            "immutable_history": True,
            "never_exposes_secrets": True,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list(self, *, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(r) for r in self._docs[-limit:]]

    def get(self, doc_id: str) -> dict[str, Any] | None:
        with self._lock:
            for row in self._docs:
                if str(row.get("id")) == str(doc_id):
                    return deepcopy(row)
        return None

    def append(self, doc: dict[str, Any]) -> dict[str, Any]:
        row = redact(dict(doc))
        with self._lock:
            self._docs.append(row)
            self._persist()
            return deepcopy(row)

    def upsert(
        self,
        doc_id: str,
        mutator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Replace by id via mutator(old)->new. Never deletes history copies."""
        with self._lock:
            for i, row in enumerate(self._docs):
                if str(row.get("id")) == str(doc_id):
                    updated = redact(mutator(deepcopy(row)))
                    updated["id"] = doc_id
                    updated["updated_at"] = utc_iso()
                    self._docs[i] = updated
                    self._persist()
                    copied: dict[str, Any] = deepcopy(updated)
                    return copied
        return None

    def count(self) -> int:
        with self._lock:
            return len(self._docs)


class PostgresDocumentStore:
    """Durable document store backed by ``public.cop_documents``.

    Same interface as :class:`JsonDocumentStore`. Used in Production so
    customer documents (support tickets) survive deploys: the Railway service
    has no volume, so the JSON file was lost on every restart (17 Nov 2026).
    Order is by creation time; ``list`` returns the newest ``limit`` rows in
    ascending order, like the JSON store.
    """

    _TIMEOUT_S = 4.0

    def __init__(self, collection: str) -> None:
        self._collection = collection
        self._lock = threading.Lock()

    @staticmethod
    def _dp() -> Any:
        from app.infrastructure.persistence import direct_postgres as dp

        return dp

    @staticmethod
    def _doc(raw: Any) -> dict[str, Any]:
        if isinstance(raw, str):
            raw = json.loads(raw)
        return dict(raw) if isinstance(raw, dict) else {}

    def list(self, *, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._dp().fetch(
            "SELECT doc FROM public.cop_documents WHERE collection = $1 "
            "ORDER BY created_at DESC, id DESC LIMIT $2",
            self._collection,
            int(limit),
            timeout=self._TIMEOUT_S,
        )
        return [self._doc(r["doc"]) for r in reversed(rows)]

    def get(self, doc_id: str) -> dict[str, Any] | None:
        rows = self._dp().fetch(
            "SELECT doc FROM public.cop_documents WHERE collection = $1 AND id = $2",
            self._collection,
            str(doc_id),
            timeout=self._TIMEOUT_S,
        )
        return self._doc(rows[0]["doc"]) if rows else None

    def append(self, doc: dict[str, Any]) -> dict[str, Any]:
        row = redact(dict(doc))
        doc_id = str(row.get("id") or "")
        if not doc_id:
            raise ValueError("document id is required")
        self._dp().execute(
            "INSERT INTO public.cop_documents (collection, id, doc) "
            "VALUES ($1, $2, $3::jsonb)",
            self._collection,
            doc_id,
            json.dumps(row, default=str),
            timeout=self._TIMEOUT_S,
        )
        return deepcopy(row)

    def upsert(
        self,
        doc_id: str,
        mutator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any] | None:
        with self._lock:
            before = self.get(doc_id)
            if before is None:
                return None
            updated = redact(mutator(deepcopy(before)))
            updated["id"] = doc_id
            updated["updated_at"] = utc_iso()
            self._dp().execute(
                "UPDATE public.cop_documents SET doc = $3::jsonb, updated_at = now() "
                "WHERE collection = $1 AND id = $2",
                self._collection,
                str(doc_id),
                json.dumps(updated, default=str),
                timeout=self._TIMEOUT_S,
            )
            copied: dict[str, Any] = deepcopy(updated)
            return copied

    def count(self) -> int:
        rows = self._dp().fetch(
            "SELECT count(*) AS n FROM public.cop_documents WHERE collection = $1",
            self._collection,
            timeout=self._TIMEOUT_S,
        )
        return int(rows[0]["n"]) if rows else 0


def durable_document_store(
    filename: str, collection_key: str
) -> JsonDocumentStore | PostgresDocumentStore:
    """Postgres when available (Production), JSON file otherwise (tests/local)."""
    try:
        from app.infrastructure.persistence import direct_postgres as dp

        if dp.direct_postgres_available():
            return PostgresDocumentStore(collection_key)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("durable_store_postgres_unavailable")
    return JsonDocumentStore(filename, collection_key)
