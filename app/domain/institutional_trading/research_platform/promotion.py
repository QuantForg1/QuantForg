"""Controlled deployment / promotion workflow — explicit approval required."""

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
    PROMOTION_STAGES,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PromotionRecord:
    id: str
    artifact_type: str  # model | experiment | optimization | variant
    artifact_id: str
    from_stage: str
    to_stage: str
    requested_by: str
    approved_by: str | None
    status: str  # pending | approved | rejected
    at: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def next_stage(current: str) -> str | None:
    try:
        i = PROMOTION_STAGES.index(current)
    except ValueError:
        return PROMOTION_STAGES[0]
    if i + 1 >= len(PROMOTION_STAGES):
        return None
    return PROMOTION_STAGES[i + 1]


@dataclass
class PromotionWorkflow:
    _rows: list[PromotionRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "promotion_workflow_v10.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = []
            for row in raw.get("promotions", []):
                if isinstance(row, dict):
                    rows.append(PromotionRecord(**row))
            with self._lock:
                self._rows = rows[-DEFAULT_RESEARCH_CONFIG.max_promotions :]
        except Exception:
            logger.exception("promotion_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "promotions": [p.to_dict() for p in self._rows],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("promotion_persist_failed")

    def request(
        self,
        *,
        artifact_type: str,
        artifact_id: str,
        from_stage: str,
        requested_by: str,
        reason: str,
    ) -> PromotionRecord:
        to_stage = next_stage(from_stage) or from_stage
        if to_stage == "Production" and DEFAULT_RESEARCH_CONFIG.auto_promote_to_production:
            raise RuntimeError("Auto-promote to production is forbidden")
        rec = PromotionRecord(
            id=str(uuid4()),
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            from_stage=from_stage if from_stage in PROMOTION_STAGES else "Development",
            to_stage=to_stage,
            requested_by=requested_by,
            approved_by=None,
            status="pending",
            at=datetime.now(UTC).isoformat(),
            reason=reason,
        )
        with self._lock:
            self._rows.append(rec)
        self._persist()
        return rec

    def decide(
        self,
        promotion_id: str,
        *,
        approved: bool,
        approved_by: str,
        reason: str = "",
    ) -> PromotionRecord | None:
        updated: PromotionRecord | None = None
        with self._lock:
            for i, p in enumerate(self._rows):
                if p.id == promotion_id:
                    if approved and p.to_stage == "Production":
                        # Explicit approval still does not auto-wire live trading
                        logger.warning(
                            "production_promotion_approved_manual_cutover_required",
                            id=p.id,
                            artifact_id=p.artifact_id,
                        )
                    updated = PromotionRecord(
                        **{
                            **p.to_dict(),
                            "status": "approved" if approved else "rejected",
                            "approved_by": approved_by,
                            "reason": reason or p.reason,
                            "at": datetime.now(UTC).isoformat(),
                        }
                    )
                    self._rows[i] = updated
                    break
        if updated is not None:
            self._persist()
        return updated

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._rows if p.status == "pending"]

    def history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [p.to_dict() for p in reversed(rows)]


_WF: PromotionWorkflow | None = None
_LOCK = threading.Lock()


def get_promotion_workflow() -> PromotionWorkflow:
    global _WF
    with _LOCK:
        if _WF is None:
            _WF = PromotionWorkflow()
        return _WF
