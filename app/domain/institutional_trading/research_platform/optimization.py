"""Optimization Studio — parameter search records (never auto-apply)."""

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
)
from core.logging import get_logger

logger = get_logger(__name__)


OPTIMIZABLE_PARAMS = (
    "confidence_threshold",
    "risk_pct",
    "atr_multiplier",
    "session_filters",
    "opportunity_scoring_weights",
    "position_management",
)


@dataclass
class OptimizationRun:
    id: str
    at: str
    author: str
    target: str
    search_space: dict[str, Any]
    best_params: dict[str, Any]
    best_score: float | None
    metrics: dict[str, Any]
    notes: str
    applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["applied"] = False
        return d


def score_candidate(metrics: dict[str, Any]) -> float:
    """Simple research score — higher better; not used for live."""
    wr = float(metrics.get("win_rate") or 0) / 100.0
    pf = float(metrics.get("profit_factor") or 0)
    dd = float(metrics.get("drawdown") or 0) / 100.0
    sharpe = float(metrics.get("sharpe") or 0)
    return round(wr * 40 + min(pf, 3) * 20 + max(0.0, 1.0 - dd) * 20 + max(0.0, sharpe) * 20, 3)


@dataclass
class OptimizationStudio:
    _runs: list[OptimizationRun] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "optimization_runs_v10.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = []
            for row in raw.get("runs", []):
                if isinstance(row, dict):
                    rows.append(
                        OptimizationRun(
                            id=str(row.get("id") or uuid4()),
                            at=str(row.get("at") or ""),
                            author=str(row.get("author") or ""),
                            target=str(row.get("target") or ""),
                            search_space=dict(row.get("search_space") or {}),
                            best_params=dict(row.get("best_params") or {}),
                            best_score=row.get("best_score"),
                            metrics=dict(row.get("metrics") or {}),
                            notes=str(row.get("notes") or ""),
                            applied=False,
                        )
                    )
            with self._lock:
                self._runs = rows[-DEFAULT_RESEARCH_CONFIG.max_optimization_runs :]
        except Exception:
            logger.exception("optimization_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "runs": [r.to_dict() for r in self._runs],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("optimization_persist_failed")

    def record_run(
        self,
        *,
        author: str,
        target: str,
        search_space: dict[str, Any],
        candidates: list[dict[str, Any]],
        notes: str = "",
    ) -> OptimizationRun:
        """candidates: list of {params, metrics} — pick best by score; never apply."""
        if DEFAULT_RESEARCH_CONFIG.auto_apply_optimizations:
            raise RuntimeError("Auto-apply optimizations is forbidden")
        best = None
        best_score = None
        best_metrics: dict[str, Any] = {}
        for c in candidates:
            m = dict(c.get("metrics") or {})
            s = score_candidate(m)
            if best_score is None or s > best_score:
                best_score = s
                best = dict(c.get("params") or {})
                best_metrics = m
        run = OptimizationRun(
            id=str(uuid4()),
            at=datetime.now(UTC).isoformat(),
            author=author,
            target=target if target in OPTIMIZABLE_PARAMS else target,
            search_space=dict(search_space),
            best_params=best or {},
            best_score=best_score,
            metrics=best_metrics,
            notes=notes,
            applied=False,
        )
        with self._lock:
            self._runs.append(run)
            if len(self._runs) > DEFAULT_RESEARCH_CONFIG.max_optimization_runs:
                self._runs = self._runs[-DEFAULT_RESEARCH_CONFIG.max_optimization_runs :]
        self._persist()
        logger.info(
            "optimization_run_recorded",
            id=run.id,
            target=run.target,
            applied=False,
        )
        return run

    def queue(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in reversed(self._runs[-50:])]


_STUDIO: OptimizationStudio | None = None
_LOCK = threading.Lock()


def get_optimization_studio() -> OptimizationStudio:
    global _STUDIO
    with _LOCK:
        if _STUDIO is None:
            _STUDIO = OptimizationStudio()
        return _STUDIO
