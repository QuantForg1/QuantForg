"""Continuous Improvement Engine — advisory insights only."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImprovementInsight:
    id: str
    at: str
    kind: str
    message: str
    auto_deploy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at,
            "kind": self.kind,
            "message": self.message,
            "auto_deploy": False,
        }


@dataclass
class ContinuousImprovementEngine:
    _insights: list[ImprovementInsight] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def generate(self, context: dict[str, Any] | None = None) -> list[ImprovementInsight]:
        ctx = context or {}
        out: list[ImprovementInsight] = []

        def emit(kind: str, message: str) -> None:
            insight = ImprovementInsight(
                id=str(uuid4()),
                at=datetime.now(UTC).isoformat(),
                kind=kind,
                message=message,
                auto_deploy=False,
            )
            out.append(insight)
            logger.info("continuous_improvement_insight", kind=kind, auto_deploy=False)

        experiments = ctx.get("experiments_by_status") or {}
        if int(experiments.get("Completed", 0) or 0) > 0:
            emit("strategy_testing", "Completed experiments deserve further out-of-sample validation.")
        if int(experiments.get("Running", 0) or 0) == 0:
            emit("strategy_testing", "No running experiments — consider drafting a controlled research trial.")

        rankings = ctx.get("symbol_rankings") or {}
        worst = (rankings.get("worst_symbols") or [])[:1]
        if worst:
            emit(
                "symbols",
                f"{worst[0].get('symbol')} requires more data / caution (weak profit factor).",
            )
        sess = rankings.get("most_profitable_session")
        if sess and str(sess.get("session", "")).lower() in {"asian", "asia"}:
            emit("sessions", "Asian session historically underperforms — investigate filters.")

        opt_queue = ctx.get("optimization_queue") or []
        if opt_queue:
            emit(
                "optimization",
                f"Optimization queue has {len(opt_queue)} run(s) worth investigating (do not auto-apply).",
            )

        models_pending = ctx.get("models_pending") or 0
        if models_pending:
            emit("models", f"{models_pending} model(s) pending review before any promotion.")

        weights = ctx.get("weight_multipliers") or {}
        unstable = [k for k, v in weights.items() if isinstance(v, (int, float)) and (v < 0.7 or v > 1.3)]
        if unstable:
            emit(
                "ai_weights",
                f"AI weights appear unstable for: {', '.join(unstable[:5])}.",
            )

        emit(
            "evidence",
            "Collect 2–4 weeks of demo/low-risk live data (win rate, PF, DD, Sharpe, RR, latency, slippage, calibration) before Production promotion.",
        )

        with self._lock:
            self._insights.extend(out)
            if len(self._insights) > 500:
                self._insights = self._insights[-500:]
        return out

    def recent(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._insights[-max(1, limit) :]
        return [i.to_dict() for i in reversed(rows)]


_ENG: ContinuousImprovementEngine | None = None
_LOCK = threading.Lock()


def get_continuous_improvement() -> ContinuousImprovementEngine:
    global _ENG
    with _LOCK:
        if _ENG is None:
            _ENG = ContinuousImprovementEngine()
        return _ENG
