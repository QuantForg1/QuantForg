"""IRL isolated store — process memory + optional JSON under data/irl/.

Never writes production / OMS / ops Postgres tables.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_research_lab.models import (
    ExperimentStatus,
    ResearchVerdict,
    sanitize_candidate_params,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "irl" / "workspace.json"


class IrlStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._path = path or DEFAULT_PATH
        self._experiments: dict[str, dict[str, Any]] = {}
        self._jobs: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._notes: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._experiments = dict(raw.get("experiments") or {})
        self._jobs = dict(raw.get("jobs") or {})
        self._reports = dict(raw.get("reports") or {})
        self._notes = dict(raw.get("notes") or {})

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "irl_v1",
                "production_isolated": True,
                "writes_production_tables": False,
                "experiments": self._experiments,
                "jobs": self._jobs,
                "reports": self._reports,
                "notes": self._notes,
                "saved_at": datetime.now(UTC).isoformat(),
            }
            self._path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except OSError:
            # Research store is best-effort; never raise into production paths.
            pass

    def create_experiment(
        self,
        *,
        name: str,
        description: str = "",
        author: str = "researcher",
        candidate_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        exp_id = str(uuid4())
        row = {
            "uuid": exp_id,
            "name": name[:128],
            "description": description[:2000],
            "author": author[:128],
            "created_at": now,
            "updated_at": now,
            "status": ExperimentStatus.DRAFT.value,
            "candidate_params": sanitize_candidate_params(candidate_params),
            "statistics": None,
            "significance": None,
            "benchmark": None,
            "verdict": ResearchVerdict.PENDING.value,
            "last_job_id": None,
        }
        with self._lock:
            self._experiments[exp_id] = row
            self._persist()
        return deepcopy(row)

    def update_experiment(self, exp_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            row = self._experiments.get(exp_id)
            if not row:
                return None
            if "name" in updates and updates["name"]:
                row["name"] = str(updates["name"])[:128]
            if "description" in updates:
                row["description"] = str(updates["description"])[:2000]
            if "candidate_params" in updates:
                row["candidate_params"] = sanitize_candidate_params(updates["candidate_params"])
            if "status" in updates and updates["status"] in {s.value for s in ExperimentStatus}:
                row["status"] = updates["status"]
            if "verdict" in updates and updates["verdict"] in {v.value for v in ResearchVerdict}:
                row["verdict"] = updates["verdict"]
            for key in ("statistics", "significance", "benchmark", "last_job_id"):
                if key in updates:
                    row[key] = updates[key]
            row["updated_at"] = datetime.now(UTC).isoformat()
            self._persist()
            return deepcopy(row)

    def get_experiment(self, exp_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._experiments.get(exp_id)
            return deepcopy(row) if row else None

    def list_experiments(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._experiments.values(),
                key=lambda r: r.get("updated_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]

    def save_job(self, job: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._jobs[job["job_id"]] = deepcopy(job)
            if len(self._jobs) > 400:
                # drop oldest
                ordered = sorted(self._jobs.items(), key=lambda kv: kv[1].get("created_at") or "")
                for k, _ in ordered[: len(self._jobs) - 300]:
                    del self._jobs[k]
            self._persist()
            return deepcopy(job)

    def list_jobs(self, *, limit: int = 50, experiment_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._jobs.values())
        if experiment_id:
            rows = [r for r in rows if r.get("experiment_id") == experiment_id]
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return [deepcopy(r) for r in rows[:limit]]

    def save_report(self, report: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._reports[report["report_id"]] = deepcopy(report)
            self._persist()
            return deepcopy(report)

    def list_reports(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = sorted(
                self._reports.values(),
                key=lambda r: r.get("created_at") or "",
                reverse=True,
            )
            return [deepcopy(r) for r in rows[:limit]]

    def add_note(self, experiment_id: str, *, author: str, body: str) -> dict[str, Any]:
        note = {
            "note_id": str(uuid4()),
            "experiment_id": experiment_id,
            "author": author[:128],
            "body": body[:4000],
            "created_at": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            bucket = self._notes.setdefault(experiment_id, [])
            bucket.append(note)
            self._persist()
            return deepcopy(note)

    def list_notes(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._notes.get(experiment_id, []))
