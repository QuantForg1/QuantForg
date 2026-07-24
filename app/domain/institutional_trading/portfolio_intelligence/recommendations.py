"""Portfolio AI recommendations — advisory only."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
)
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioRecommendation:
    id: str
    at: str
    kind: str
    message: str
    auto_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "at": self.at,
            "kind": self.kind,
            "message": self.message,
            "auto_applied": False,
        }


@dataclass
class PortfolioRecommendationEngine:
    _rows: list[PortfolioRecommendation] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def generate(
        self,
        *,
        allocation: dict[str, Any],
        optimization: dict[str, Any],
        protection: dict[str, Any],
        regime: dict[str, Any],
        risk_budget_pct: float,
    ) -> list[PortfolioRecommendation]:
        if DEFAULT_PI_CONFIG.recommendations_auto_apply:
            raise RuntimeError("Auto-apply recommendations is forbidden")
        out: list[PortfolioRecommendation] = []

        def emit(kind: str, message: str) -> None:
            rec = PortfolioRecommendation(
                id=str(uuid4()),
                at=datetime.now(UTC).isoformat(),
                kind=kind,
                message=message,
                auto_applied=False,
            )
            out.append(rec)
            logger.info("portfolio_recommendation", kind=kind, message=message, auto_applied=False)

        emit(
            "risk_budget",
            f"Today's optimal risk budget is {risk_budget_pct}%.",
        )
        for a in (allocation.get("allocations") or [])[:1]:
            if str(a.get("symbol") or "").upper() in {"XAUUSD", "GOLD"}:
                if float(a.get("share_pct") or 0) >= 35:
                    emit("reduce_gold", "Reduce Gold exposure — share is elevated.")
        for msg in optimization.get("rebalance_recommendations") or []:
            emit("optimizer", str(msg))
        if protection.get("new_exposure_scale", 1) < 1:
            emit(
                "protection",
                f"New exposure scaled to {protection.get('new_exposure_scale')} by capital protection.",
            )
        if regime.get("regime") == "GLOBAL_RISK_OFF":
            emit("regime", "Increase USD diversification / reduce risk-on book.")
        if float(optimization.get("correlation") or 0) >= 0.6:
            emit("correlation", "Current portfolio correlation is high.")

        with self._lock:
            self._rows.extend(out)
            if len(self._rows) > DEFAULT_PI_CONFIG.max_recommendations:
                self._rows = self._rows[-DEFAULT_PI_CONFIG.max_recommendations :]
        return out

    def recent(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]


_ENG: PortfolioRecommendationEngine | None = None
_LOCK = threading.Lock()


def get_portfolio_recommendation_engine() -> PortfolioRecommendationEngine:
    global _ENG
    with _LOCK:
        if _ENG is None:
            _ENG = PortfolioRecommendationEngine()
        return _ENG
