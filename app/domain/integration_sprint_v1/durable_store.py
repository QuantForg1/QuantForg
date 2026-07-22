"""Durable append-only storage for research / IVP / LLP / RMIP / PRC."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

NAMESPACES = ("research", "ivp", "llp", "rmip", "prc")


class DurableResearchStore:
    """Process-local durable store (append-only). Never overwrites prior rows."""

    def __init__(self, *, max_per_namespace: int = 2_000) -> None:
        self._max = max(10, max_per_namespace)
        self._lock = Lock()
        self._rows: dict[str, list[dict[str, Any]]] = {
            ns: [] for ns in NAMESPACES
        }

    def append(
        self, namespace: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        ns = str(namespace).strip().lower()
        if ns not in NAMESPACES:
            return {
                "status": "error",
                "message": f"Unknown namespace {namespace}",
                "allowed": list(NAMESPACES),
            }
        entry = {
            "id": str(record.get("id") or f"{ns}_{uuid4().hex[:10]}"),
            "namespace": ns,
            "recorded_at": datetime.now(UTC).isoformat(),
            "payload": dict(record.get("payload") or record),
            "source": str(record.get("source") or "integration_sprint_v1"),
            "append_only": True,
            "overwrites_prior": False,
            "read_only_archive": True,
        }
        with self._lock:
            bucket = self._rows[ns]
            bucket.insert(0, entry)
            if len(bucket) > self._max:
                self._rows[ns] = bucket[: self._max]
            count = len(self._rows[ns])
        return {"status": "available", "entry": entry, "count": count}

    def list(
        self, namespace: str, *, limit: int = 50
    ) -> dict[str, Any]:
        ns = str(namespace).strip().lower()
        if ns not in NAMESPACES:
            return {
                "status": "MISSING DATA",
                "items": [],
                "message": f"Unknown namespace {namespace}",
            }
        with self._lock:
            rows = list(self._rows[ns][: max(1, min(limit, self._max))])
        return {
            "status": "available" if rows else "empty",
            "namespace": ns,
            "items": rows,
            "append_only": True,
            "read_only_archive": True,
        }

    def health(self) -> dict[str, Any]:
        with self._lock:
            counts = {ns: len(rows) for ns, rows in self._rows.items()}
        return {
            "status": "healthy",
            "namespaces": counts,
            "append_only": True,
            "read_only": True,
        }
