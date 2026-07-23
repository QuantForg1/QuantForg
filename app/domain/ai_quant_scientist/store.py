"""AQS isolated store — recommendations & reports under data/aqs/ only."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.ai_quant_scientist.models import RecommendationStatus

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "aqs" / "workspace.json"


class AqsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._recommendations: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._recommendations = dict(raw.get("recommendations") or {})
        self._reports = dict(raw.get("reports") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "aqs_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "recommendations": self._recommendations,
                "reports": self._reports,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def upsert_recommendation(self, row: dict[str, Any]) -> dict[str, Any]:
        rid = str(row.get("id") or uuid4())
        now = datetime.now(UTC).isoformat()
        with self._lock:
            existing = self._recommendations.get(rid)
            if existing:
                merged = {**existing, **row, "id": rid, "updated_at": now}
                # Preserve operator status if already set beyond Open
                if existing.get("status") in {
                    RecommendationStatus.ACCEPTED.value,
                    RecommendationStatus.REJECTED.value,
                    RecommendationStatus.ARCHIVED.value,
                } and row.get("status") == RecommendationStatus.OPEN.value:
                    merged["status"] = existing["status"]
            else:
                merged = {
                    **row,
                    "id": rid,
                    "created_at": row.get("created_at") or now,
                    "updated_at": now,
                    "status": row.get("status") or RecommendationStatus.OPEN.value,
                }
            self._recommendations[rid] = merged
            self._persist()
            return deepcopy(merged)

    def set_status(self, rid: str, status: str) -> dict[str, Any] | None:
        allowed = {s.value for s in RecommendationStatus}
        if status not in allowed:
            raise ValueError("invalid_status")
        with self._lock:
            row = self._recommendations.get(rid)
            if not row:
                return None
            row = dict(row)
            row["status"] = status
            row["updated_at"] = datetime.now(UTC).isoformat()
            row["status_note"] = (
                "Accepted never changes production automatically — "
                "governance workflow required"
            )
            self._recommendations[rid] = row
            self._persist()
            return deepcopy(row)

    def list_recommendations(
        self, *, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._recommendations.values())
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        return [deepcopy(r) for r in rows[:limit]]

    def get_recommendation(self, rid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._recommendations.get(rid)
            return deepcopy(row) if row else None

    def save_report(self, report: dict[str, Any]) -> dict[str, Any]:
        rid = str(report.get("report_id") or uuid4())
        now = datetime.now(UTC).isoformat()
        row = {**report, "report_id": rid, "created_at": report.get("created_at") or now}
        with self._lock:
            self._reports[rid] = row
            if len(self._reports) > 100:
                ordered = sorted(
                    self._reports.items(), key=lambda kv: kv[1].get("created_at") or ""
                )
                for k, _ in ordered[: len(self._reports) - 80]:
                    del self._reports[k]
            self._persist()
            return deepcopy(row)

    def list_reports(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._reports.values(),
                key=lambda r: r.get("created_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]
