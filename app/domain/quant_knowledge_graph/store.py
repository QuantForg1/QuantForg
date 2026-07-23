"""QKG isolated snapshot cache under data/qkg/ — never production tables."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qkg" / "graph_snapshot.json"


class QkgStore:
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
        if isinstance(raw, dict):
            self._snapshot = raw

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                **self._snapshot,
                "schema": "qkg_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def save_snapshot(self, graph: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._snapshot = {
                "nodes": graph.get("nodes") or [],
                "edges": graph.get("edges") or [],
                "stats": graph.get("stats") or {},
                "availability": graph.get("availability") or {},
                "built_at": graph.get("built_at") or datetime.now(UTC).isoformat(),
            }
            self._persist()
            return deepcopy(self._snapshot)

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot) if self._snapshot else {}
