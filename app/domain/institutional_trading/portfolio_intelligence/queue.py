"""Opportunity queue — ranked portfolio-aware candidates (not instant fire)."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
)
from app.domain.institutional_trading.portfolio_intelligence.state import PortfolioState


@dataclass
class QueueItem:
    id: str
    at: str
    symbol: str
    direction: str
    confidence: int
    expected_rr: float
    risk: float
    correlation: float
    priority: int
    expected_duration: str
    estimated_profit: float
    estimated_portfolio_impact: float
    opportunity_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpportunityQueue:
    _items: list[QueueItem] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def rebuild(
        self,
        opportunities: list[dict[str, Any]],
        state: PortfolioState,
        *,
        risk_budget_pct: float,
    ) -> list[QueueItem]:
        items: list[QueueItem] = []
        ranked = sorted(
            opportunities,
            key=lambda o: (
                int(o.get("opportunity_score") or 0),
                int(o.get("ai_confidence") or o.get("confidence") or 0),
            ),
            reverse=True,
        )
        for i, o in enumerate(ranked[: DEFAULT_PI_CONFIG.max_queue], start=1):
            score = int(o.get("opportunity_score") or 0)
            conf = int(o.get("ai_confidence") or o.get("confidence") or 0)
            rr = float(o.get("expected_rr") or 0)
            corr = 0.0
            sym = str(o.get("symbol") or "").upper()
            row = state.correlation_matrix.get(sym)
            if isinstance(row, dict) and state.open_symbols:
                vals = []
                for peer in state.open_symbols:
                    try:
                        vals.append(abs(float(row.get(peer, 0))))
                    except Exception:
                        pass
                corr = max(vals) if vals else 0.0
            impact = round((score / 100.0) * (risk_budget_pct / 100.0) * (1.0 - corr), 4)
            est_profit = round(rr * conf / 100.0 * risk_budget_pct, 3)
            items.append(
                QueueItem(
                    id=str(uuid4()),
                    at=datetime.now(UTC).isoformat(),
                    symbol=sym,
                    direction=str(o.get("direction") or "NONE"),
                    confidence=conf,
                    expected_rr=rr,
                    risk=round(risk_budget_pct * (1.0 + corr), 3),
                    correlation=round(corr, 3),
                    priority=i,
                    expected_duration=str(o.get("expected_duration") or "intraday"),
                    estimated_profit=est_profit,
                    estimated_portfolio_impact=impact,
                    opportunity_score=score,
                )
            )
        with self._lock:
            self._items = items
        return items

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._items),
                "items": [i.to_dict() for i in self._items],
            }


_QUEUE: OpportunityQueue | None = None
_LOCK = threading.Lock()


def get_opportunity_queue() -> OpportunityQueue:
    global _QUEUE
    with _LOCK:
        if _QUEUE is None:
            _QUEUE = OpportunityQueue()
        return _QUEUE
