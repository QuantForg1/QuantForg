"""Phase A decision journal — observe-only audit of entry decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass
class DecisionJournalEntry:
    candidate_id: str
    symbol: str
    strategy: str
    direction: str
    signal_state: str
    market_data_state: str
    safety_state: str
    risk_state: str
    sizing_state: str
    portfolio_state: str
    execution_state: str
    kill_switch_state: str
    burst_latch_state: str
    final_control_state: str
    first_blocking_gate: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "direction": self.direction,
            "signal_state": self.signal_state,
            "market_data_state": self.market_data_state,
            "safety_state": self.safety_state,
            "risk_state": self.risk_state,
            "sizing_state": self.sizing_state,
            "portfolio_state": self.portfolio_state,
            "execution_state": self.execution_state,
            "kill_switch_state": self.kill_switch_state,
            "burst_latch_state": self.burst_latch_state,
            "final_control_state": self.final_control_state,
            "first_blocking_gate": self.first_blocking_gate or "UNKNOWN_REASON",
            "timestamp": self.timestamp,
        }


@dataclass
class DecisionJournal:
    entries: list[DecisionJournalEntry] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(self, **kwargs: Any) -> DecisionJournalEntry:
        entry = DecisionJournalEntry(
            candidate_id=str(kwargs.get("candidate_id") or uuid4()),
            symbol=str(kwargs.get("symbol") or ""),
            strategy=str(kwargs.get("strategy") or ""),
            direction=str(kwargs.get("direction") or ""),
            signal_state=str(kwargs.get("signal_state") or "UNKNOWN"),
            market_data_state=str(kwargs.get("market_data_state") or "UNKNOWN"),
            safety_state=str(kwargs.get("safety_state") or "UNKNOWN"),
            risk_state=str(kwargs.get("risk_state") or "UNKNOWN"),
            sizing_state=str(kwargs.get("sizing_state") or "UNKNOWN"),
            portfolio_state=str(kwargs.get("portfolio_state") or "UNKNOWN"),
            execution_state=str(kwargs.get("execution_state") or "UNKNOWN"),
            kill_switch_state=str(kwargs.get("kill_switch_state") or "UNKNOWN"),
            burst_latch_state=str(kwargs.get("burst_latch_state") or "UNKNOWN"),
            final_control_state=str(kwargs.get("final_control_state") or "BLOCK"),
            first_blocking_gate=str(
                kwargs.get("first_blocking_gate") or "UNKNOWN_REASON"
            ),
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
