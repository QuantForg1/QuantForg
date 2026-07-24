"""AI weight optimizer — gradual scoring multipliers only; never changes rules."""

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
    OPTIMIZER_FACTORS,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OptimizationLogEntry:
    id: str
    at: str
    win: bool
    before: dict[str, float]
    after: dict[str, float]
    factors_seen: dict[str, int]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at,
            "win": self.win,
            "before": dict(self.before),
            "after": dict(self.after),
            "factors_seen": dict(self.factors_seen),
            "detail": self.detail,
        }


@dataclass
class WeightOptimizerStore:
    multipliers: dict[str, float] = field(
        default_factory=lambda: {k: 1.0 for k in OPTIMIZER_FACTORS}
    )
    logs: list[OptimizationLogEntry] = field(default_factory=list)
    updates: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "ai_weight_optimizer_v7.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            mult = raw.get("multipliers", {})
            with self._lock:
                for k in OPTIMIZER_FACTORS:
                    if k in mult:
                        self.multipliers[k] = float(mult[k])
                self.updates = int(raw.get("updates") or 0)
                for row in raw.get("logs", [])[-DEFAULT_AI_VALIDATION_CONFIG.max_optimization_logs :]:
                    if isinstance(row, dict):
                        self.logs.append(
                            OptimizationLogEntry(
                                id=str(row.get("id") or uuid4()),
                                at=str(row.get("at") or ""),
                                win=bool(row.get("win")),
                                before=dict(row.get("before") or {}),
                                after=dict(row.get("after") or {}),
                                factors_seen=dict(row.get("factors_seen") or {}),
                                detail=str(row.get("detail") or ""),
                            )
                        )
        except Exception:
            logger.exception("weight_optimizer_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "updates": self.updates,
                    "multipliers": dict(self.multipliers),
                    "logs": [e.to_dict() for e in self.logs[-DEFAULT_AI_VALIDATION_CONFIG.max_optimization_logs :]],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("weight_optimizer_persist_failed")

    def optimize_from_trade(
        self,
        *,
        win: bool,
        factor_scores: dict[str, int] | None = None,
    ) -> OptimizationLogEntry | None:
        cfg = DEFAULT_AI_VALIDATION_CONFIG
        if not cfg.optimizer_enabled:
            return None
        scores = {k: int((factor_scores or {}).get(k, 50)) for k in OPTIMIZER_FACTORS}
        with self._lock:
            before = dict(self.multipliers)
            step = cfg.optimizer_step
            for k in OPTIMIZER_FACTORS:
                score = scores[k]
                if win and score >= 60:
                    self.multipliers[k] = min(cfg.optimizer_max, self.multipliers[k] + step)
                elif (not win) and score >= 60:
                    self.multipliers[k] = max(cfg.optimizer_min, self.multipliers[k] - step)
            after = dict(self.multipliers)
            self.updates += 1
            entry = OptimizationLogEntry(
                id=str(uuid4()),
                at=datetime.now(UTC).isoformat(),
                win=win,
                before=before,
                after=after,
                factors_seen=scores,
                detail="gradual multiplier nudge — trading rules unchanged",
            )
            self.logs.append(entry)
            if len(self.logs) > cfg.max_optimization_logs:
                self.logs = self.logs[-cfg.max_optimization_logs :]
        self._persist()
        logger.info(
            "ai_weight_optimization",
            win=win,
            updates=self.updates,
            detail=entry.detail,
        )
        return entry

    def apply_to_weights(self, base_weights: dict[str, int | float]) -> dict[str, float]:
        with self._lock:
            out: dict[str, float] = {}
            for k, w in base_weights.items():
                key = k.lower()
                m = self.multipliers.get(key, 1.0)
                out[k] = max(0.01, float(w) * m)
            return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "updates": self.updates,
                "multipliers": dict(self.multipliers),
                "optimizer_enabled": DEFAULT_AI_VALIDATION_CONFIG.optimizer_enabled,
                "recent_logs": [e.to_dict() for e in self.logs[-20:]],
                "note": "Weights only — trading rules never auto-changed",
            }


_STORE: WeightOptimizerStore | None = None
_LOCK = threading.Lock()


def get_weight_optimizer() -> WeightOptimizerStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = WeightOptimizerStore()
        return _STORE
