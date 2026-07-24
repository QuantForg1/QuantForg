"""ISE isolated store under data/ise/ — never production tables."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "ise" / "workspace.json"


class IseStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._simulations: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._simulations = dict(raw.get("simulations") or {})
        self._reports = dict(raw.get("reports") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "ise_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "digital_twin": True,
                "simulations": self._simulations,
                "reports": self._reports,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def upsert_simulation(self, row: dict[str, Any]) -> dict[str, Any]:
        sid = str(row.get("simulation_id") or uuid4())
        now = datetime.now(UTC).isoformat()
        with self._lock:
            merged = {
                **(self._simulations.get(sid) or {}),
                **row,
                "simulation_id": sid,
                "updated_at": now,
                "created_at": row.get("created_at")
                or (self._simulations.get(sid) or {}).get("created_at")
                or now,
                "production_isolated": True,
            }
            self._simulations[sid] = merged
            if len(self._simulations) > 150:
                ordered = sorted(
                    self._simulations.items(),
                    key=lambda kv: kv[1].get("updated_at") or "",
                )
                for k, _ in ordered[: len(self._simulations) - 100]:
                    del self._simulations[k]
            self._persist()
            return deepcopy(merged)

    def list_simulations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._simulations.values(),
                key=lambda r: r.get("updated_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]

    def get_simulation(self, sid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._simulations.get(sid)
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

    def knowledge_nodes(self, *, limit: int = 40) -> list[dict[str, Any]]:
        """Descriptors for Quant Knowledge Graph — isolated research nodes only."""
        rows = self.list_simulations(limit=limit)
        nodes = []
        for s in rows:
            nodes.append(
                {
                    "id": f"simulation:{s.get('simulation_id')}",
                    "type": "Research Experiments",
                    "label": str(s.get("title") or s.get("mode") or "ISE Simulation"),
                    "properties": {
                        "mode": s.get("mode"),
                        "scenario": s.get("scenario"),
                        "metrics": s.get("metrics"),
                        "digital_twin": True,
                        "never_modifies_production": True,
                    },
                    "source_subsystem": "institutional_simulation_engine",
                }
            )
        return nodes
