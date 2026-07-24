"""AI opportunity history — top opportunities per day + replay."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.ai_validation.config import (
    DEFAULT_AI_VALIDATION_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OpportunityRecord:
    id: str
    day: str
    rank: int
    symbol: str
    direction: str
    opportunity_score: int
    confidence: int
    traded: bool
    result: str | None  # win | loss | flat | None
    skip_reason: str | None
    at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "day": self.day,
            "rank": self.rank,
            "symbol": self.symbol,
            "direction": self.direction,
            "opportunity_score": self.opportunity_score,
            "confidence": self.confidence,
            "traded": self.traded,
            "result": self.result,
            "skip_reason": self.skip_reason,
            "at": self.at,
        }


@dataclass
class OpportunityHistoryStore:
    _by_day: dict[str, list[OpportunityRecord]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "opportunity_history_v7.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            by: dict[str, list[OpportunityRecord]] = {}
            for day, rows in (raw.get("days") or {}).items():
                by[day] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    by[day].append(
                        OpportunityRecord(
                            id=str(row.get("id") or uuid4()),
                            day=str(day),
                            rank=int(row.get("rank") or 0),
                            symbol=str(row.get("symbol") or ""),
                            direction=str(row.get("direction") or ""),
                            opportunity_score=int(row.get("opportunity_score") or 0),
                            confidence=int(row.get("confidence") or 0),
                            traded=bool(row.get("traded")),
                            result=row.get("result"),
                            skip_reason=row.get("skip_reason"),
                            at=str(row.get("at") or ""),
                        )
                    )
            with self._lock:
                self._by_day = by
        except Exception:
            logger.exception("opportunity_history_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                days = {
                    d: [r.to_dict() for r in rows]
                    for d, rows in self._by_day.items()
                }
                # prune
                keys = sorted(days.keys())
                keep = keys[-DEFAULT_AI_VALIDATION_CONFIG.max_opportunity_days :]
                days = {k: days[k] for k in keep}
                payload = {"updated_at": datetime.now(UTC).isoformat(), "days": days}
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("opportunity_history_persist_failed")

    def record_daily_top(
        self,
        opportunities: list[dict[str, Any]],
        *,
        day: str | None = None,
    ) -> list[OpportunityRecord]:
        """Store top 10 for the day (overwrite same ranks)."""
        day_key = day or datetime.now(UTC).strftime("%Y-%m-%d")
        rows: list[OpportunityRecord] = []
        for i, opp in enumerate(opportunities[:10], start=1):
            rows.append(
                OpportunityRecord(
                    id=str(uuid4()),
                    day=day_key,
                    rank=int(opp.get("rank") or i),
                    symbol=str(opp.get("symbol") or ""),
                    direction=str(opp.get("direction") or ""),
                    opportunity_score=int(opp.get("opportunity_score") or 0),
                    confidence=int(opp.get("ai_confidence") or opp.get("confidence") or 0),
                    traded=bool(opp.get("traded", False)),
                    result=opp.get("result"),
                    skip_reason=opp.get("skip_reason"),
                    at=datetime.now(UTC).isoformat(),
                )
            )
        with self._lock:
            self._by_day[day_key] = rows
        self._persist()
        return rows

    def mark_traded(
        self,
        *,
        symbol: str,
        day: str | None = None,
        result: str | None = None,
    ) -> None:
        day_key = day or datetime.now(UTC).strftime("%Y-%m-%d")
        with self._lock:
            rows = self._by_day.get(day_key) or []
            for r in rows:
                if r.symbol.upper() == symbol.upper():
                    r.traded = True
                    if result is not None:
                        r.result = result
        self._persist()

    def replay(self, day: str | None = None) -> dict[str, Any]:
        day_key = day or datetime.now(UTC).strftime("%Y-%m-%d")
        with self._lock:
            rows = [r.to_dict() for r in self._by_day.get(day_key, [])]
            days = sorted(self._by_day.keys(), reverse=True)[:30]
        return {"day": day_key, "opportunities": rows, "available_days": days}


_STORE: OpportunityHistoryStore | None = None
_LOCK = threading.Lock()


def get_opportunity_history_store() -> OpportunityHistoryStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = OpportunityHistoryStore()
        return _STORE
