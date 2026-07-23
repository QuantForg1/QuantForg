"""Read-only warehouse store — deep copies only; never touches production."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.domain.institutional_data_warehouse.models import DATA_DOMAINS, DataDomain
from app.domain.institutional_data_warehouse.schema import normalize_warehouse_record


class InstitutionalDataWarehouse:
    """In-process analytics warehouse with logical datasets per domain."""

    def __init__(self) -> None:
        self._datasets: dict[str, list[dict[str, Any]]] = {
            d: [] for d in DATA_DOMAINS
        }
        self._lock = Lock()
        self._ingest_batches = 0
        self._ingest_history: list[dict[str, Any]] = []
        self._created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def clear(self, domain: DataDomain | None = None) -> None:
        """Clear warehouse copies only — never production sources."""
        with self._lock:
            if domain is None:
                for d in DATA_DOMAINS:
                    self._datasets[d] = []
            else:
                self._datasets[str(domain)] = []

    def replace_rows(self, domain: DataDomain, rows: list[dict[str, Any]]) -> int:
        """Replace warehouse domain copies (already-normalized envelopes)."""
        if domain not in DATA_DOMAINS:
            raise ValueError(f"Unknown warehouse domain: {domain}")
        with self._lock:
            self._datasets[domain] = [deepcopy(r) for r in rows]
            return len(self._datasets[domain])

    def ingest(
        self,
        domain: DataDomain,
        rows: list[dict[str, Any]] | None,
        *,
        environment: str | None = None,
        replace: bool = False,
        source: str | None = None,
    ) -> int:
        if domain not in DATA_DOMAINS:
            raise ValueError(f"Unknown warehouse domain: {domain}")
        normalized: list[dict[str, Any]] = []
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue
            rec = normalize_warehouse_record(
                deepcopy(raw),
                domain=domain,
                environment=environment,
                source=source,
            )
            if rec is not None:
                normalized.append(rec)
        with self._lock:
            if replace:
                self._datasets[domain] = normalized
            else:
                self._datasets[domain].extend(normalized)
            self._ingest_batches += 1
            self._ingest_history.append(
                {
                    "at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "domain": domain,
                    "records": len(normalized),
                    "replace": replace,
                }
            )
            if len(self._ingest_history) > 200:
                self._ingest_history = self._ingest_history[-150:]
            return len(normalized)

    def list(
        self,
        domain: DataDomain,
        *,
        limit: int = 200,
        q: str | None = None,
        since: str | None = None,
        until: str | None = None,
        session: str | None = None,
        environment: str | None = None,
        strategy_version: str | None = None,
    ) -> list[dict[str, Any]]:
        if domain not in DATA_DOMAINS:
            raise ValueError(f"Unknown warehouse domain: {domain}")
        with self._lock:
            rows = deepcopy(self._datasets[domain])
        out: list[dict[str, Any]] = []
        for row in rows:
            if session and str(row.get("session") or "") != session:
                continue
            if environment and str(row.get("environment") or "") != environment:
                continue
            if strategy_version and str(row.get("strategy_version") or "") != (
                strategy_version
            ):
                continue
            ts = str(row.get("timestamp") or "")
            if since and ts and ts < since:
                continue
            if until and ts and ts > until:
                continue
            if q:
                blob = str(row).lower()
                if q.lower() not in blob:
                    continue
            out.append(row)
        out.sort(key=lambda r: str(r.get("timestamp") or ""))
        if limit and len(out) > limit:
            out = out[-limit:]
        return out

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {d: len(self._datasets[d]) for d in DATA_DOMAINS}

    def event_flow(self, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._ingest_history[-limit:])

    def storage_stats(self) -> dict[str, Any]:
        counts = self.counts()
        total = sum(counts.values())
        approx_bytes = 0
        with self._lock:
            for rows in self._datasets.values():
                for row in rows:
                    approx_bytes += len(str(row))
        return {
            "total_records": total,
            "approx_bytes": approx_bytes,
            "approx_mb": round(approx_bytes / (1024 * 1024), 4),
            "domains_populated": sum(1 for n in counts.values() if n > 0),
            "domains_total": len(DATA_DOMAINS),
            "ingest_batches": self._ingest_batches,
            "created_at": self._created_at,
            "read_only": True,
        }

    def inventory(self) -> dict[str, Any]:
        counts = self.counts()
        return {
            "status": "available",
            "domains": counts,
            "total_records": sum(counts.values()),
            "ingest_batches": self._ingest_batches,
            "storage": self.storage_stats(),
            "event_flow": self.event_flow(limit=20),
            "read_only": True,
            "never_modifies_production_records": True,
            "immutable_event_storage": True,
        }


_WAREHOUSE = InstitutionalDataWarehouse()


def get_warehouse() -> InstitutionalDataWarehouse:
    return _WAREHOUSE
