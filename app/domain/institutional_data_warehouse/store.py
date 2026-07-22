"""Read-only warehouse store — deep copies only; never touches production."""

from __future__ import annotations

from copy import deepcopy
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

    def clear(self, domain: DataDomain | None = None) -> None:
        """Clear warehouse copies only — never production sources."""
        with self._lock:
            if domain is None:
                for d in DATA_DOMAINS:
                    self._datasets[d] = []
            else:
                self._datasets[str(domain)] = []

    def ingest(
        self,
        domain: DataDomain,
        rows: list[dict[str, Any]] | None,
        *,
        environment: str | None = None,
        replace: bool = False,
    ) -> int:
        if domain not in DATA_DOMAINS:
            raise ValueError(f"Unknown warehouse domain: {domain}")
        normalized: list[dict[str, Any]] = []
        for raw in rows or []:
            if not isinstance(raw, dict):
                continue
            # Deep-copy source before normalize — never mutate caller rows
            rec = normalize_warehouse_record(
                deepcopy(raw), domain=domain, environment=environment
            )
            if rec is not None:
                normalized.append(rec)
        with self._lock:
            if replace:
                self._datasets[domain] = normalized
            else:
                self._datasets[domain].extend(normalized)
            self._ingest_batches += 1
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

    def inventory(self) -> dict[str, Any]:
        counts = self.counts()
        return {
            "status": "available",
            "domains": counts,
            "total_records": sum(counts.values()),
            "ingest_batches": self._ingest_batches,
            "read_only": True,
            "never_modifies_production_records": True,
        }


_WAREHOUSE = InstitutionalDataWarehouse()


def get_warehouse() -> InstitutionalDataWarehouse:
    return _WAREHOUSE
