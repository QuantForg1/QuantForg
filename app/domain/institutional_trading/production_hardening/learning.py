"""Continuous learning — gradual Opportunity Score weight adjustment.

Does not overwrite rules. Adjusts multipliers slowly from closed-trade outcomes.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.institutional_trading.production_hardening.config import (
    DEFAULT_HARDENING_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)

FACTOR_KEYS = (
    "confidence",
    "trend",
    "momentum",
    "liquidity",
    "volatility",
    "spread",
    "expected_rr",
    "session",
)


@dataclass
class LearningWeightStore:
    multipliers: dict[str, float] = field(
        default_factory=lambda: {k: 1.0 for k in FACTOR_KEYS}
    )
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
            self._path = base / "opportunity_learning_weights.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            mult = raw.get("multipliers", {})
            with self._lock:
                for k in FACTOR_KEYS:
                    if k in mult:
                        self.multipliers[k] = float(mult[k])
                self.updates = int(raw.get("updates") or 0)
        except Exception:
            logger.exception("learning_weights_load_failed")

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
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("learning_weights_persist_failed")

    def observe_trade(
        self,
        *,
        win: bool,
        factor_scores: dict[str, int] | None = None,
    ) -> None:
        """Nudge multipliers toward factors that correlated with wins."""
        cfg = DEFAULT_HARDENING_CONFIG
        if not cfg.learning_enabled:
            return
        scores = factor_scores or {}
        step = cfg.learning_weight_step
        with self._lock:
            for k in FACTOR_KEYS:
                score = int(scores.get(k) or 50)
                # If win and factor was strong (>60), gently increase; else decrease
                if win and score >= 60:
                    self.multipliers[k] = min(
                        cfg.learning_weight_max, self.multipliers[k] + step
                    )
                elif (not win) and score >= 60:
                    self.multipliers[k] = max(
                        cfg.learning_weight_min, self.multipliers[k] - step
                    )
            self.updates += 1
        self._persist()

    def apply_to_weights(self, base_weights: dict[str, int]) -> dict[str, int]:
        """Return integer weights scaled by learned multipliers (rules preserved)."""
        with self._lock:
            out: dict[str, int] = {}
            for k, w in base_weights.items():
                m = self.multipliers.get(k, 1.0)
                out[k] = max(1, int(round(w * m)))
            return out

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "updates": self.updates,
                "multipliers": dict(self.multipliers),
                "learning_enabled": DEFAULT_HARDENING_CONFIG.learning_enabled,
            }


_STORE: LearningWeightStore | None = None
_LOCK = threading.Lock()


def get_learning_weight_store() -> LearningWeightStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = LearningWeightStore()
        return _STORE
