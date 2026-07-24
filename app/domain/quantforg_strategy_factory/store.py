"""QSF store — factory-isolated workflow state under data/qsf/."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "qsf" / "workspace.json"


class QsfStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._snapshot: dict[str, Any] = {}
        self._stage_overrides: dict[str, str] = {}
        self._approvals: list[dict[str, Any]] = []
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
        self._stage_overrides = dict(raw.get("stage_overrides") or {})
        self._approvals = list(raw.get("approvals") or [])
        self._reports = list(raw.get("reports") or [])

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "qsf_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "never_deploys_strategies": True,
                "snapshot": self._snapshot,
                "stage_overrides": self._stage_overrides,
                "approvals": self._approvals[-200:],
                "reports": self._reports[-50:],
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def get_stage_overrides(self) -> dict[str, str]:
        with self._lock:
            return deepcopy(self._stage_overrides)

    def set_stage(self, strategy_id: str, stage: str) -> None:
        with self._lock:
            self._stage_overrides[strategy_id] = stage
            self._persist()

    def record_approval(
        self,
        *,
        strategy_id: str,
        from_stage: str,
        to_stage: str,
        approver: str,
        decision: str,
        comment: str | None = None,
        work_item_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            entry = {
                "approval_id": str(uuid4()),
                "strategy_id": strategy_id,
                "work_item_id": work_item_id,
                "from_stage": from_stage,
                "to_stage": to_stage,
                "approver": approver,
                "decision": decision,
                "comment": comment,
                "created_at": datetime.now(UTC).isoformat(),
                "note": "Human approval recorded in QSF isolation only",
                "never_modifies_production": True,
                "never_deploys_strategies": True,
                "never_executes_trades": True,
            }
            self._approvals.append(entry)
            if decision == "approved":
                self._stage_overrides[strategy_id] = to_stage
            self._persist()
            return deepcopy(entry)

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(r) for r in list(reversed(self._approvals[-limit:]))]

    def save_snapshot(self, snap: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._snapshot = {
                "work_item_count": len(snap.get("work_items") or []),
                "queue_depth": len(snap.get("approval_queue") or []),
                "observed_at": snap.get("observed_at") or datetime.now(UTC).isoformat(),
                "elapsed_ms": snap.get("elapsed_ms"),
                "workflow_consistency": snap.get("workflow_consistency"),
                "evidence_integrity": snap.get("evidence_integrity"),
            }
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

    def get_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._snapshot)
