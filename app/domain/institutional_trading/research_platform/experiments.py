"""Experiment Manager — controlled research experiments (never auto-modify production)."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.research_platform.config import (
    DEFAULT_RESEARCH_CONFIG,
    EXPERIMENT_STATUSES,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Experiment:
    id: str
    name: str
    description: str
    author: str
    start_date: str
    end_date: str | None
    sample_size: int
    success_criteria: str
    status: str
    variant: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentStore:
    _rows: list[Experiment] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "research_experiments_v10.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = []
            for row in raw.get("experiments", []):
                if not isinstance(row, dict):
                    continue
                rows.append(
                    Experiment(
                        id=str(row.get("id") or uuid4()),
                        name=str(row.get("name") or ""),
                        description=str(row.get("description") or ""),
                        author=str(row.get("author") or ""),
                        start_date=str(row.get("start_date") or ""),
                        end_date=row.get("end_date"),
                        sample_size=int(row.get("sample_size") or 0),
                        success_criteria=str(row.get("success_criteria") or ""),
                        status=str(row.get("status") or "Draft"),
                        variant=dict(row.get("variant") or {}),
                        results=dict(row.get("results") or {}),
                        created_at=str(row.get("created_at") or ""),
                        updated_at=str(row.get("updated_at") or ""),
                    )
                )
            with self._lock:
                self._rows = rows[-DEFAULT_RESEARCH_CONFIG.max_experiments :]
        except Exception:
            logger.exception("experiments_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "experiments": [e.to_dict() for e in self._rows],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("experiments_persist_failed")

    def create(
        self,
        *,
        name: str,
        description: str,
        author: str,
        sample_size: int = 0,
        success_criteria: str = "",
        start_date: str | None = None,
        end_date: str | None = None,
        variant: dict[str, Any] | None = None,
        status: str = "Draft",
    ) -> Experiment:
        if status not in EXPERIMENT_STATUSES:
            status = "Draft"
        now = datetime.now(UTC).isoformat()
        exp = Experiment(
            id=str(uuid4()),
            name=name,
            description=description,
            author=author,
            start_date=start_date or now[:10],
            end_date=end_date,
            sample_size=int(sample_size),
            success_criteria=success_criteria,
            status=status,
            variant=dict(variant or {}),
            results={},
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._rows.append(exp)
            if len(self._rows) > DEFAULT_RESEARCH_CONFIG.max_experiments:
                self._rows = self._rows[-DEFAULT_RESEARCH_CONFIG.max_experiments :]
        self._persist()
        logger.info("research_experiment_created", id=exp.id, status=exp.status, auto_prod=False)
        return exp

    def set_status(self, experiment_id: str, status: str) -> Experiment | None:
        if status not in EXPERIMENT_STATUSES:
            return None
        updated: Experiment | None = None
        with self._lock:
            for i, e in enumerate(self._rows):
                if e.id == experiment_id:
                    updated = Experiment(
                        **{
                            **e.to_dict(),
                            "status": status,
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    self._rows[i] = updated
                    break
        if updated is not None:
            self._persist()
        return updated

    def attach_results(self, experiment_id: str, results: dict[str, Any]) -> Experiment | None:
        updated: Experiment | None = None
        with self._lock:
            for i, e in enumerate(self._rows):
                if e.id == experiment_id:
                    updated = Experiment(
                        **{
                            **e.to_dict(),
                            "results": dict(results),
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    self._rows[i] = updated
                    break
        if updated is not None:
            self._persist()
        return updated

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._rows)
        if status:
            rows = [r for r in rows if r.status == status]
        return [r.to_dict() for r in reversed(rows)]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            by = {s: 0 for s in EXPERIMENT_STATUSES}
            for e in self._rows:
                by[e.status] = by.get(e.status, 0) + 1
            return {"total": len(self._rows), "by_status": by}


_STORE: ExperimentStore | None = None
_LOCK = threading.Lock()


def get_experiment_store() -> ExperimentStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ExperimentStore()
        return _STORE
