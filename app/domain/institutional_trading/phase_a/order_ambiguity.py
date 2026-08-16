"""Phase A UNKNOWN / RECONCILIATION_REQUIRED order ambiguity gate.

When execution outcome is ambiguous, block NEW risk until reconciled.
Does not remove existing decision-hash dedupe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4


class AmbiguityState(str, Enum):
    CLEAR = "CLEAR"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RESOLVED_FILLED = "RESOLVED_FILLED"
    RESOLVED_REJECTED = "RESOLVED_REJECTED"
    RESOLVED_CANCELLED = "RESOLVED_CANCELLED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass
class AmbiguousOrderRecord:
    order_id: str
    decision_hash: str
    symbol: str
    side: str
    state: AmbiguityState
    reason: str
    created_at: str
    updated_at: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "decision_hash": self.decision_hash,
            "symbol": self.symbol,
            "side": self.side,
            "state": self.state.value,
            "reason": self.reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evidence": dict(self.evidence),
        }


@dataclass
class OrderAmbiguityGate:
    """Blocks new entries while unresolved UNKNOWN / RECONCILIATION_REQUIRED."""

    open: dict[str, AmbiguousOrderRecord] = field(default_factory=dict)
    history: list[AmbiguousOrderRecord] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def has_blocking_ambiguity(self) -> bool:
        with self._lock:
            return any(
                r.state
                in {
                    AmbiguityState.UNKNOWN,
                    AmbiguityState.RECONCILIATION_REQUIRED,
                    AmbiguityState.MANUAL_REVIEW_REQUIRED,
                }
                for r in self.open.values()
            )

    def blocking_reason(self) -> str | None:
        with self._lock:
            for r in self.open.values():
                if r.state in {
                    AmbiguityState.UNKNOWN,
                    AmbiguityState.RECONCILIATION_REQUIRED,
                    AmbiguityState.MANUAL_REVIEW_REQUIRED,
                }:
                    return f"{r.state.value}:{r.symbol}:{r.reason}"
            return None

    def mark_unknown(
        self,
        *,
        decision_hash: str,
        symbol: str,
        side: str = "",
        reason: str,
        evidence: dict[str, Any] | None = None,
    ) -> AmbiguousOrderRecord:
        now = datetime.now(UTC).isoformat()
        oid = str(uuid4())
        rec = AmbiguousOrderRecord(
            order_id=oid,
            decision_hash=str(decision_hash or "")[:128],
            symbol=str(symbol or "").upper(),
            side=str(side or ""),
            state=AmbiguityState.UNKNOWN,
            reason=str(reason or "ambiguous_execution")[:240],
            created_at=now,
            updated_at=now,
            evidence=dict(evidence or {}),
        )
        with self._lock:
            # Escalate UNKNOWN → RECONCILIATION_REQUIRED immediately (mandatory)
            rec.state = AmbiguityState.RECONCILIATION_REQUIRED
            self.open[oid] = rec
            self.history.append(rec)
            if len(self.history) > 200:
                self.history = self.history[-200:]
        return rec

    def resolve(
        self,
        order_id: str,
        *,
        outcome: AmbiguityState,
        evidence: dict[str, Any] | None = None,
    ) -> AmbiguousOrderRecord | None:
        if outcome not in {
            AmbiguityState.RESOLVED_FILLED,
            AmbiguityState.RESOLVED_REJECTED,
            AmbiguityState.RESOLVED_CANCELLED,
            AmbiguityState.MANUAL_REVIEW_REQUIRED,
            AmbiguityState.CLEAR,
        }:
            raise ValueError(f"invalid resolve outcome: {outcome}")
        with self._lock:
            rec = self.open.get(order_id)
            if rec is None:
                return None
            rec.state = (
                AmbiguityState.CLEAR
                if outcome is AmbiguityState.CLEAR
                else outcome
            )
            rec.updated_at = datetime.now(UTC).isoformat()
            if evidence:
                rec.evidence.update(evidence)
            if outcome is not AmbiguityState.MANUAL_REVIEW_REQUIRED:
                self.open.pop(order_id, None)
            return rec

    def reconcile_from_mt5(
        self,
        order_id: str,
        *,
        position_found: bool | None,
        order_found: bool | None,
        filled: bool | None = None,
        rejected: bool | None = None,
        cancelled: bool | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> AmbiguityState:
        """Deterministic reconcile helper — never invents fills."""
        ev = dict(evidence or {})
        ev.update(
            {
                "position_found": position_found,
                "order_found": order_found,
                "filled": filled,
                "rejected": rejected,
                "cancelled": cancelled,
            }
        )
        if filled is True or position_found is True:
            outcome = AmbiguityState.RESOLVED_FILLED
        elif rejected is True:
            outcome = AmbiguityState.RESOLVED_REJECTED
        elif cancelled is True:
            outcome = AmbiguityState.RESOLVED_CANCELLED
        elif position_found is False and order_found is False and filled is False:
            # Confirmed absent on all books → treat as rejected/no-fill
            outcome = AmbiguityState.RESOLVED_REJECTED
        else:
            outcome = AmbiguityState.MANUAL_REVIEW_REQUIRED
        self.resolve(order_id, outcome=outcome, evidence=ev)
        return outcome

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "blocking": self.has_blocking_ambiguity(),
                "blocking_reason": self.blocking_reason(),
                "open": [r.to_dict() for r in self.open.values()],
                "recent": [r.to_dict() for r in self.history[-10:]],
            }

    def to_persist(self) -> dict[str, Any]:
        with self._lock:
            return {
                "phase_a_ambiguous_orders": [r.to_dict() for r in self.open.values()],
            }

    def hydrate(self, state: dict[str, Any]) -> None:
        rows = state.get("phase_a_ambiguous_orders")
        if not isinstance(rows, list):
            return
        with self._lock:
            self.open.clear()
            for raw in rows:
                if not isinstance(raw, dict):
                    continue
                try:
                    st = AmbiguityState(str(raw.get("state") or "RECONCILIATION_REQUIRED"))
                except Exception:
                    st = AmbiguityState.RECONCILIATION_REQUIRED
                if st not in {
                    AmbiguityState.UNKNOWN,
                    AmbiguityState.RECONCILIATION_REQUIRED,
                    AmbiguityState.MANUAL_REVIEW_REQUIRED,
                }:
                    continue
                oid = str(raw.get("order_id") or uuid4())
                rec = AmbiguousOrderRecord(
                    order_id=oid,
                    decision_hash=str(raw.get("decision_hash") or ""),
                    symbol=str(raw.get("symbol") or ""),
                    side=str(raw.get("side") or ""),
                    state=st,
                    reason=str(raw.get("reason") or ""),
                    created_at=str(raw.get("created_at") or datetime.now(UTC).isoformat()),
                    updated_at=str(raw.get("updated_at") or datetime.now(UTC).isoformat()),
                    evidence=dict(raw.get("evidence") or {})
                    if isinstance(raw.get("evidence"), dict)
                    else {},
                )
                self.open[oid] = rec
