"""AI Model Registry — versions with explicit approval for production."""

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
    MODEL_APPROVAL,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModelVersion:
    id: str
    version: str
    author: str
    date: str
    performance: dict[str, Any]
    notes: str
    approval_status: str
    promoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModelRegistry:
    _models: list[ModelVersion] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "model_registry_v10.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = []
            for row in raw.get("models", []):
                if isinstance(row, dict):
                    rows.append(
                        ModelVersion(
                            id=str(row.get("id") or uuid4()),
                            version=str(row.get("version") or ""),
                            author=str(row.get("author") or ""),
                            date=str(row.get("date") or ""),
                            performance=dict(row.get("performance") or {}),
                            notes=str(row.get("notes") or ""),
                            approval_status=str(row.get("approval_status") or "pending"),
                            promoted=bool(row.get("promoted", False)),
                        )
                    )
            with self._lock:
                self._models = rows[-DEFAULT_RESEARCH_CONFIG.max_models :]
        except Exception:
            logger.exception("model_registry_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "models": [m.to_dict() for m in self._models],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("model_registry_persist_failed")

    def register(
        self,
        *,
        version: str,
        author: str,
        performance: dict[str, Any] | None = None,
        notes: str = "",
    ) -> ModelVersion:
        m = ModelVersion(
            id=str(uuid4()),
            version=version,
            author=author,
            date=datetime.now(UTC).isoformat(),
            performance=dict(performance or {}),
            notes=notes,
            approval_status="pending",
            promoted=False,
        )
        with self._lock:
            self._models.append(m)
        self._persist()
        return m

    def set_approval(self, model_id: str, status: str) -> ModelVersion | None:
        if status not in MODEL_APPROVAL:
            return None
        updated: ModelVersion | None = None
        with self._lock:
            for i, m in enumerate(self._models):
                if m.id == model_id:
                    updated = ModelVersion(**{**m.to_dict(), "approval_status": status})
                    self._models[i] = updated
                    break
        if updated is not None:
            self._persist()
        return updated

    def approve_for_production(self, model_id: str) -> ModelVersion | None:
        """Mark approved — does NOT auto-wire into live trading."""
        if DEFAULT_RESEARCH_CONFIG.auto_promote_to_production:
            raise RuntimeError("Auto-promote to production is forbidden")
        m = self.set_approval(model_id, "approved")
        if m is None:
            return None
        updated: ModelVersion | None = None
        with self._lock:
            for i, row in enumerate(self._models):
                if row.id == model_id:
                    updated = ModelVersion(**{**row.to_dict(), "promoted": False})
                    # promoted flag stays False until explicit promotion workflow stage=Production
                    self._models[i] = updated
                    break
        if updated is not None:
            self._persist()
            logger.info("model_approved", id=model_id, auto_live=False)
            return updated
        return m

    def list(self, *, approval: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._models)
        if approval:
            rows = [m for m in rows if m.approval_status == approval]
        return [m.to_dict() for m in reversed(rows)]

    def approved(self) -> list[dict[str, Any]]:
        return self.list(approval="approved")


_REG: ModelRegistry | None = None
_LOCK = threading.Lock()


def get_model_registry() -> ModelRegistry:
    global _REG
    with _LOCK:
        if _REG is None:
            _REG = ModelRegistry()
        return _REG
