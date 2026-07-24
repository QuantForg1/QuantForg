"""QSMR isolated registry cache under data/qsmr/ — never production tables."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qsmr" / "workspace.json"


class QsmrStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._strategies: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._snapshot: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._strategies = dict(raw.get("strategies") or {})
        self._reports = dict(raw.get("reports") or {})
        self._snapshot = dict(raw.get("snapshot") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "qsmr_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "deploys_strategies": False,
                "strategies": self._strategies,
                "reports": self._reports,
                "snapshot": self._snapshot,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def upsert_strategy(self, row: dict[str, Any]) -> dict[str, Any]:
        sid = str(row.get("strategy_id") or uuid4())
        now = datetime.now(UTC).isoformat()
        with self._lock:
            existing = self._strategies.get(sid) or {}
            merged = {
                **existing,
                **row,
                "strategy_id": sid,
                "updated_at": now,
                "created_at": row.get("created_at")
                or existing.get("created_at")
                or now,
            }
            self._strategies[sid] = merged
            if len(self._strategies) > 200:
                ordered = sorted(
                    self._strategies.items(),
                    key=lambda kv: kv[1].get("updated_at") or "",
                )
                for k, _ in ordered[: len(self._strategies) - 150]:
                    del self._strategies[k]
            self._persist()
            return deepcopy(merged)

    def list_strategies(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._strategies.values(),
                key=lambda r: r.get("updated_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]

    def get_strategy(self, sid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._strategies.get(sid)
            return deepcopy(row) if row else None

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
