"""QDIE store — advisory decision snapshots under data/qdie/ (never production)."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qdie" / "workspace.json"


class QdieStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._snapshot: dict[str, Any] = {}
        self._history: list[dict[str, Any]] = []
        self._reports: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._snapshot = dict(raw.get("snapshot") or {})
        self._history = list(raw.get("history") or [])
        self._reports = list(raw.get("reports") or [])

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "qdie_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "advisory_only": True,
                "snapshot": self._snapshot,
                "history": self._history[-200:],
                "reports": self._reports[-50:],
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
                "recommendation_count": len(snap.get("recommendations") or []),
                "observed_at": snap.get("observed_at") or datetime.now(UTC).isoformat(),
                "elapsed_ms": snap.get("elapsed_ms"),
                "decision_consistency": snap.get("decision_consistency"),
                "evidence_consistency": snap.get("evidence_consistency"),
                "explainability": snap.get("explainability_validation"),
            }
            # Append history entries from recommendations
            for r in snap.get("recommendations") or []:
                if isinstance(r, dict):
                    self._history.append(
                        {
                            "decision_id": r.get("decision_id"),
                            "created_at": r.get("created_at"),
                            "category": r.get("decision_category"),
                            "priority": r.get("priority"),
                            "title": r.get("title"),
                            "human_approval_status": r.get("human_approval_status"),
                        }
                    )
            self._history = self._history[-200:]
            self._persist()
            return deepcopy(self._snapshot)

    def save_report(self, report: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            row = {**report, "recorded_at": datetime.now(UTC).isoformat()}
            self._reports.append(row)
            self._reports = self._reports[-50:]
            self._persist()
            return deepcopy(row)

    def list_reports(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._reports[-limit:])

    def list_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._history[-limit:])

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot)
