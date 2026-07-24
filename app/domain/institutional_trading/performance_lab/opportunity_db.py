"""Opportunity outcome database — every evaluation including skips."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.performance_lab.config import DEFAULT_LAB_CONFIG
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OpportunityOutcome:
    id: str
    symbol: str
    at: str
    ai_confidence: int
    opportunity_score: int
    traded: bool
    outcome: str | None  # win | loss | flat
    hypothetical_outcome: str | None  # if skipped
    skip_reason: str | None
    session: str | None = None
    regime: str | None = None
    strategy: str | None = None
    direction: str | None = None
    expected_rr: float | None = None
    slippage: float | None = None
    latency_ms: float | None = None
    spread: float | None = None
    pnl: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OpportunityOutcomeStore:
    max_rows: int = DEFAULT_LAB_CONFIG.max_opportunities
    _rows: list[OpportunityOutcome] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "opportunity_outcomes_v8.jsonl"

    def record(self, row: OpportunityOutcome) -> OpportunityOutcome:
        with self._lock:
            self._rows.append(row)
            if len(self._rows) > self.max_rows:
                self._rows = self._rows[-self.max_rows :]
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row.to_dict()) + "\n")
        except Exception:
            logger.exception("opportunity_outcome_persist_failed")
        return row

    def record_evaluation(
        self,
        *,
        symbol: str,
        ai_confidence: int,
        opportunity_score: int,
        traded: bool,
        skip_reason: str | None = None,
        outcome: str | None = None,
        hypothetical_outcome: str | None = None,
        session: str | None = None,
        regime: str | None = None,
        strategy: str | None = None,
        direction: str | None = None,
        expected_rr: float | None = None,
        slippage: float | None = None,
        latency_ms: float | None = None,
        spread: float | None = None,
        pnl: float | None = None,
    ) -> OpportunityOutcome:
        return self.record(
            OpportunityOutcome(
                id=str(uuid4()),
                symbol=symbol,
                at=datetime.now(UTC).isoformat(),
                ai_confidence=int(ai_confidence),
                opportunity_score=int(opportunity_score),
                traded=traded,
                outcome=outcome,
                hypothetical_outcome=hypothetical_outcome,
                skip_reason=skip_reason,
                session=session,
                regime=regime,
                strategy=strategy,
                direction=direction,
                expected_rr=expected_rr,
                slippage=slippage,
                latency_ms=latency_ms,
                spread=spread,
                pnl=pnl,
            )
        )

    def recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]

    def filtered(
        self,
        *,
        symbol: str | None = None,
        session: str | None = None,
        regime: str | None = None,
        strategy: str | None = None,
    ) -> list[OpportunityOutcome]:
        with self._lock:
            rows = list(self._rows)
        if symbol:
            rows = [r for r in rows if r.symbol.upper() == symbol.upper()]
        if session:
            rows = [r for r in rows if (r.session or "").lower() == session.lower()]
        if regime:
            rows = [r for r in rows if (r.regime or "").lower() == regime.lower()]
        if strategy:
            rows = [r for r in rows if (r.strategy or "").lower() == strategy.lower()]
        return rows

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._rows)
            traded = sum(1 for r in self._rows if r.traded)
            skipped = total - traded
        return {"total": total, "traded": traded, "skipped": skipped}


_STORE: OpportunityOutcomeStore | None = None
_LOCK = threading.Lock()


def get_opportunity_outcome_store() -> OpportunityOutcomeStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = OpportunityOutcomeStore()
        return _STORE
