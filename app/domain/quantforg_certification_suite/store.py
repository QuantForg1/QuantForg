"""QCS isolated cache under data/qcs/ — never production tables."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qcs" / "workspace.json"


class QcsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._reports: dict[str, dict[str, Any]] = {}
        self._snapshot: dict[str, Any] = {}
        self._timeline: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._reports = dict(raw.get("reports") or {})
        self._snapshot = dict(raw.get("snapshot") or {})
        self._timeline = list(raw.get("timeline") or [])

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "qcs_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "approves_releases_automatically": False,
                "reports": self._reports,
                "snapshot": self._snapshot,
                "timeline": self._timeline[-100:],
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def save_snapshot(self, snap: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._snapshot = {
                "scores": snap.get("scores"),
                "level": snap.get("level"),
                "blockers": snap.get("blockers"),
                "checks": snap.get("checks"),
                "observed_at": snap.get("observed_at") or datetime.now(UTC).isoformat(),
                "elapsed_ms": snap.get("elapsed_ms"),
            }
            event = {
                "at": self._snapshot["observed_at"],
                "level": snap.get("level"),
                "overall": (snap.get("scores") or {}).get(
                    "overall_institutional_readiness_score"
                ),
                "blocker_count": len(snap.get("blockers") or []),
                "note": "Observational certification assessment",
                "human_approval_required": True,
                "auto_certified": False,
            }
            self._timeline.append(event)
            self._timeline = self._timeline[-100:]
            self._persist()
            return deepcopy(self._snapshot)

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot)

    def list_timeline(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(r) for r in list(reversed(self._timeline[-limit:]))]

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
