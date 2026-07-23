"""AQC isolated store — conversations, investigations, reports under data/aqc/."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "aqc" / "workspace.json"


class AqcStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._conversations: list[dict[str, Any]] = []
        self._investigations: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._conversations = list(raw.get("conversations") or [])
        self._investigations = dict(raw.get("investigations") or {})
        self._reports = dict(raw.get("reports") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "aqc_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "conversations": self._conversations[-200:],
                "investigations": self._investigations,
                "reports": self._reports,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def append_conversation(self, row: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entry = {
            **row,
            "id": str(row.get("id") or uuid4()),
            "created_at": row.get("created_at") or now,
            "advisory_only": True,
        }
        with self._lock:
            self._conversations.append(entry)
            self._conversations = self._conversations[-200:]
            self._persist()
            return deepcopy(entry)

    def list_conversations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(reversed(self._conversations[-limit:]))
            return [deepcopy(r) for r in rows]

    def upsert_investigation(self, row: dict[str, Any]) -> dict[str, Any]:
        iid = str(row.get("id") or uuid4())
        now = datetime.now(UTC).isoformat()
        with self._lock:
            merged = {
                **(self._investigations.get(iid) or {}),
                **row,
                "id": iid,
                "updated_at": now,
                "created_at": row.get("created_at")
                or (self._investigations.get(iid) or {}).get("created_at")
                or now,
            }
            self._investigations[iid] = merged
            if len(self._investigations) > 120:
                ordered = sorted(
                    self._investigations.items(),
                    key=lambda kv: kv[1].get("updated_at") or "",
                )
                for k, _ in ordered[: len(self._investigations) - 80]:
                    del self._investigations[k]
            self._persist()
            return deepcopy(merged)

    def list_investigations(self, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._investigations.values(),
                key=lambda r: r.get("updated_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]

    def get_investigation(self, iid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._investigations.get(iid)
            return deepcopy(row) if row else None

    def save_report(self, report: dict[str, Any]) -> dict[str, Any]:
        rid = str(report.get("report_id") or uuid4())
        now = datetime.now(UTC).isoformat()
        row = {**report, "report_id": rid, "created_at": report.get("created_at") or now}
        with self._lock:
            self._reports[rid] = row
            if len(self._reports) > 80:
                ordered = sorted(
                    self._reports.items(), key=lambda kv: kv[1].get("created_at") or ""
                )
                for k, _ in ordered[: len(self._reports) - 50]:
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
