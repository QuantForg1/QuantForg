"""IRDP isolated store under data/irdp/ — governance records only."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_release_deployment.models import ReleaseStatus

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "irdp" / "workspace.json"


class IrdpStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._releases: dict[str, dict[str, Any]] = {}
        self._approvals: list[dict[str, Any]] = []
        self._rollbacks: list[dict[str, Any]] = []
        self._reports: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._releases = dict(raw.get("releases") or {})
        self._approvals = list(raw.get("approvals") or [])
        self._rollbacks = list(raw.get("rollbacks") or [])
        self._reports = dict(raw.get("reports") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "irdp_v1",
                "production_isolated": True,
                "approves_releases_automatically": False,
                "rollbacks_automatically": False,
                "releases": self._releases,
                "approvals": self._approvals[-200:],
                "rollbacks": self._rollbacks[-200:],
                "reports": self._reports,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
        except OSError:
            pass

    def upsert_release(self, row: dict[str, Any]) -> dict[str, Any]:
        rid = str(row.get("release_id") or uuid4())
        now = datetime.now(UTC).isoformat()
        with self._lock:
            existing = self._releases.get(rid) or {}
            merged = {
                **existing,
                **row,
                "release_id": rid,
                "updated_at": now,
                "created_at": row.get("created_at")
                or existing.get("created_at")
                or now,
                "status": row.get("status")
                or existing.get("status")
                or ReleaseStatus.DRAFT.value,
            }
            self._releases[rid] = merged
            if len(self._releases) > 120:
                ordered = sorted(
                    self._releases.items(),
                    key=lambda kv: kv[1].get("updated_at") or "",
                )
                for k, _ in ordered[: len(self._releases) - 80]:
                    del self._releases[k]
            self._persist()
            return deepcopy(merged)

    def get_release(self, rid: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._releases.get(rid)
            return deepcopy(row) if row else None

    def list_releases(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._releases.values(),
                key=lambda r: r.get("updated_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]

    def record_approval(self, row: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entry = {
            **row,
            "approval_id": str(row.get("approval_id") or uuid4()),
            "recorded_at": now,
            "automatic": False,
            "note": "Explicit human approval only — never automatic",
        }
        with self._lock:
            self._approvals.append(entry)
            self._approvals = self._approvals[-200:]
            self._persist()
            return deepcopy(entry)

    def list_approvals(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(reversed(self._approvals[-limit:]))
            return [deepcopy(r) for r in rows]

    def record_rollback(self, row: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        entry = {
            **row,
            "rollback_id": str(row.get("rollback_id") or uuid4()),
            "recorded_at": now,
            "automatic": False,
            "note": "Controlled rollback plan — never executed automatically by IRDP",
        }
        with self._lock:
            self._rollbacks.append(entry)
            self._rollbacks = self._rollbacks[-200:]
            self._persist()
            return deepcopy(entry)

    def list_rollbacks(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(reversed(self._rollbacks[-limit:]))
            return [deepcopy(r) for r in rows]

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
