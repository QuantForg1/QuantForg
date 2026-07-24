"""ISLM isolated registry under data/islm/ — never production tables."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_strategy_lifecycle.models import LifecycleState

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "islm" / "workspace.json"


class IslmStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._strategies: dict[str, dict[str, Any]] = {}
        self._approvals: list[dict[str, Any]] = []
        self._reports: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._strategies = dict(raw.get("strategies") or {})
        self._approvals = list(raw.get("approvals") or [])
        self._reports = dict(raw.get("reports") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "islm_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "never_auto_approves": True,
                "strategies": self._strategies,
                "approvals": self._approvals[-200:],
                "reports": self._reports,
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
            # Preserve human-set lifecycle if already beyond derived default
            merged = {
                **existing,
                **row,
                "strategy_id": sid,
                "updated_at": now,
                "created_at": row.get("created_at")
                or existing.get("created_at")
                or now,
            }
            if existing.get("lifecycle_locked"):
                merged["lifecycle_state"] = existing.get("lifecycle_state")
                merged["lifecycle_locked"] = True
            self._strategies[sid] = merged
            self._persist()
            return deepcopy(merged)

    def list_strategies(self, *, limit: int = 100) -> list[dict[str, Any]]:
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

    def record_approval(
        self,
        *,
        strategy_id: str,
        from_state: str,
        to_state: str,
        approver: str,
        decision: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Human governance only — never applies to production engines."""
        allowed = {s.value for s in LifecycleState}
        if to_state not in allowed:
            raise ValueError("invalid_lifecycle_state")
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid_decision")
        now = datetime.now(UTC).isoformat()
        entry = {
            "approval_id": str(uuid4()),
            "strategy_id": strategy_id,
            "from_state": from_state,
            "to_state": to_state,
            "approver": approver,
            "decision": decision,
            "comment": comment,
            "created_at": now,
            "never_modifies_production": True,
            "note": "Human approval recorded in ISLM isolation only",
        }
        with self._lock:
            self._approvals.append(entry)
            row = self._strategies.get(strategy_id)
            if row and decision == "approved":
                row = dict(row)
                row["lifecycle_state"] = to_state
                row["lifecycle_locked"] = True
                row["last_approver"] = approver
                row["last_approved_at"] = now
                hist = list(row.get("version_history") or [])
                hist.append(
                    {
                        "at": now,
                        "from": from_state,
                        "to": to_state,
                        "approver": approver,
                    }
                )
                row["version_history"] = hist[-50:]
                self._strategies[strategy_id] = row
            self._persist()
            return deepcopy(entry)

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(r) for r in list(reversed(self._approvals[-limit:]))]

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
