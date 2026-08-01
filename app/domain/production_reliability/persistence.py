"""File-backed persistence for Production Reliability Program."""

from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

_SECRET_KEYS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|credential|private|bearer)",
    re.I,
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_id(prefix: str = "rel") -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def data_path(filename: str) -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / "production_reliability" / filename


def redact(value: Any) -> Any:
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


class JsonDocumentStore:
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
            "never_exposes_secrets": True,
            "destructive_ops_forbidden": True,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list(self, *, limit: int = 2000) -> list[dict[str, Any]]:
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

    def upsert(self, doc_id: str, mutator) -> dict[str, Any] | None:
        with self._lock:
            for i, row in enumerate(self._docs):
                if str(row.get("id")) == str(doc_id):
                    updated = redact(mutator(deepcopy(row)))
                    updated["id"] = doc_id
                    updated["updated_at"] = utc_iso()
                    self._docs[i] = updated
                    self._persist()
                    return deepcopy(updated)
        return None

    def count(self) -> int:
        with self._lock:
            return len(self._docs)
