"""QCDM store — schema metadata snapshot under data/qcdm/ (never production)."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qcdm" / "workspace.json"


class QcdmStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._snapshot: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._snapshot = dict(raw.get("snapshot") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "qcdm_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "snapshot": self._snapshot,
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
                "schema_version": snap.get("schema_version"),
                "model_count": snap.get("model_count"),
                "observed_at": snap.get("observed_at") or datetime.now(UTC).isoformat(),
                "elapsed_ms": snap.get("elapsed_ms"),
                "schema_consistency": snap.get("schema_consistency"),
                "compatibility": snap.get("compatibility"),
                "reference_validation": snap.get("reference_validation"),
            }
            self._persist()
            return deepcopy(self._snapshot)

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot)
