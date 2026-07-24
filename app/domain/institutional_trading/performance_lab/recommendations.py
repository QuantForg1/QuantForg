"""Adaptive recommendations — advisory only; never auto-applied."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.performance_lab.config import DEFAULT_LAB_CONFIG
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Recommendation:
    id: str
    at: str
    kind: str
    message: str
    evidence: dict[str, Any]
    auto_applied: bool = False  # always False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at,
            "kind": self.kind,
            "message": self.message,
            "evidence": self.evidence,
            "auto_applied": False,
        }


@dataclass
class RecommendationEngine:
    _rows: list[Recommendation] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _emit(self, *, kind: str, message: str, evidence: dict[str, Any]) -> Recommendation:
        rec = Recommendation(
            id=str(uuid4()),
            at=datetime.now(UTC).isoformat(),
            kind=kind,
            message=message,
            evidence=evidence,
            auto_applied=False,
        )
        with self._lock:
            self._rows.append(rec)
            if len(self._rows) > DEFAULT_LAB_CONFIG.max_recommendations:
                self._rows = self._rows[-DEFAULT_LAB_CONFIG.max_recommendations :]
        logger.info(
            "performance_lab_recommendation",
            kind=kind,
            message=message,
            auto_applied=False,
        )
        return rec

    def generate_from_rankings(self, rankings: dict[str, Any]) -> list[Recommendation]:
        out: list[Recommendation] = []
        best = (rankings.get("best_symbols") or [])[:1]
        worst = (rankings.get("worst_symbols") or [])[:1]
        sess = rankings.get("most_profitable_session")
        if best:
            b = best[0]
            out.append(
                self._emit(
                    kind="symbol_strength",
                    message=f"{b.get('symbol')} currently has the best profit factor ({b.get('profit_factor')}).",
                    evidence=b,
                )
            )
        if worst:
            w = worst[0]
            out.append(
                self._emit(
                    kind="reduce_risk",
                    message=f"Reduce risk on {w.get('symbol')} (weak profit factor {w.get('profit_factor')}).",
                    evidence=w,
                )
            )
        if sess and str(sess.get("session", "")).lower() in {"asian", "asia", "tokyo"}:
            out.append(
                self._emit(
                    kind="session_threshold",
                    message="Increase confidence threshold during Asian session (weaker historical edge).",
                    evidence=dict(sess),
                )
            )
        elif sess:
            out.append(
                self._emit(
                    kind="session_edge",
                    message=f"Most profitable session recently: {sess.get('session')}.",
                    evidence=dict(sess),
                )
            )
        slip = (rankings.get("highest_slippage") or [])[:1]
        if slip:
            s = slip[0]
            out.append(
                self._emit(
                    kind="slippage",
                    message=f"Watch slippage on {s.get('symbol')} (avg {s.get('avg_slippage')}).",
                    evidence=s,
                )
            )
        return out

    def recent(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]


_ENGINE: RecommendationEngine | None = None
_LOCK = threading.Lock()


def get_recommendation_engine() -> RecommendationEngine:
    global _ENGINE
    with _LOCK:
        if _ENGINE is None:
            _ENGINE = RecommendationEngine()
        return _ENGINE
