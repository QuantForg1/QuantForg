"""Explainable trade / candidate journal — no fabricated reasons."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass
class ExplainJournalEntry:
    candidate_id: str
    symbol: str
    strategy: str
    direction: str
    signal_state: str
    rank: int | None
    rank_score: float | None
    market_data_state: str
    regime: str
    safety_state: str
    risk_state: str
    portfolio_state: str
    execution_quality_state: str
    control_state: str
    first_blocking_gate: str
    why_signalled: str
    why_ranked: str
    why_allowed: str | None
    why_blocked: str | None
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "direction": self.direction,
            "signal_state": self.signal_state,
            "rank": self.rank,
            "rank_score": self.rank_score,
            "market_data_state": self.market_data_state,
            "regime": self.regime,
            "safety_state": self.safety_state,
            "risk_state": self.risk_state,
            "portfolio_state": self.portfolio_state,
            "execution_quality_state": self.execution_quality_state,
            "control_state": self.control_state,
            "first_blocking_gate": self.first_blocking_gate or "UNKNOWN_REASON",
            "WHY_SIGNALLED": self.why_signalled or "UNKNOWN_REASON",
            "WHY_RANKED": self.why_ranked or "UNKNOWN_REASON",
            "WHY_ALLOWED": self.why_allowed,
            "WHY_BLOCKED": self.why_blocked,
            "timestamp": self.timestamp,
        }


@dataclass
class ExplainJournal:
    entries: list[ExplainJournalEntry] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(self, **kwargs: Any) -> ExplainJournalEntry:
        control = str(kwargs.get("control_state") or "UNKNOWN")
        gate = str(kwargs.get("first_blocking_gate") or "") or "UNKNOWN_REASON"
        allowed = control in {"ALLOW", "REDUCE"}
        why_allowed = None
        why_blocked = None
        if allowed:
            why_allowed = str(kwargs.get("why_allowed") or "all controls passed")
        else:
            why_blocked = str(kwargs.get("why_blocked") or gate or "UNKNOWN_REASON")

        entry = ExplainJournalEntry(
            candidate_id=str(kwargs.get("candidate_id") or uuid4()),
            symbol=str(kwargs.get("symbol") or ""),
            strategy=str(kwargs.get("strategy") or ""),
            direction=str(kwargs.get("direction") or ""),
            signal_state=str(kwargs.get("signal_state") or "UNKNOWN"),
            rank=kwargs.get("rank") if kwargs.get("rank") is not None else None,
            rank_score=(
                float(kwargs["rank_score"])
                if kwargs.get("rank_score") is not None
                else None
            ),
            market_data_state=str(kwargs.get("market_data_state") or "UNKNOWN"),
            regime=str(kwargs.get("regime") or "UNKNOWN"),
            safety_state=str(kwargs.get("safety_state") or "UNKNOWN"),
            risk_state=str(kwargs.get("risk_state") or "UNKNOWN"),
            portfolio_state=str(kwargs.get("portfolio_state") or "UNKNOWN"),
            execution_quality_state=str(
                kwargs.get("execution_quality_state") or "UNKNOWN"
            ),
            control_state=control,
            first_blocking_gate=gate,
            why_signalled=str(kwargs.get("why_signalled") or "UNKNOWN_REASON"),
            why_ranked=str(kwargs.get("why_ranked") or "UNKNOWN_REASON"),
            why_allowed=why_allowed,
            why_blocked=why_blocked,
            timestamp=str(kwargs.get("timestamp") or datetime.now(UTC).isoformat()),
        )
        with self._lock:
            self.entries.append(entry)
            if len(self.entries) > 500:
                self.entries = self.entries[-500:]
        return entry

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self.entries[-limit:]]
