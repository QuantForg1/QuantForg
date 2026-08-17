"""Canary governance — constrained review path; never grants OMS authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4


class CanaryState(str, Enum):
    SHADOW = "SHADOW"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    CANARY_APPROVED = "CANARY_APPROVED"
    CANARY = "CANARY"
    CANARY_REVIEW = "CANARY_REVIEW"
    CANARY_BLOCKED = "CANARY_BLOCKED"
    LIVE_APPROVED = "LIVE_APPROVED"
    LIVE = "LIVE"
    ROLLED_BACK = "ROLLED_BACK"
    SHADOW_ONLY = "SHADOW_ONLY"


# Auto transitions (no LIVE jump)
_AUTO = {
    CanaryState.SHADOW: {CanaryState.PROMOTION_REVIEW, CanaryState.CANARY_BLOCKED},
    CanaryState.PROMOTION_REVIEW: {
        CanaryState.CANARY_APPROVED,
        CanaryState.CANARY_BLOCKED,
    },
    CanaryState.CANARY_APPROVED: {CanaryState.CANARY, CanaryState.CANARY_BLOCKED},
    CanaryState.CANARY: {
        CanaryState.CANARY_REVIEW,
        CanaryState.ROLLED_BACK,
        CanaryState.SHADOW_ONLY,
        CanaryState.CANARY_BLOCKED,
    },
    CanaryState.CANARY_REVIEW: {
        CanaryState.LIVE_APPROVED,
        CanaryState.ROLLED_BACK,
        CanaryState.SHADOW_ONLY,
        CanaryState.CANARY_BLOCKED,
    },
    CanaryState.ROLLED_BACK: {CanaryState.SHADOW_ONLY},
}

_APPROVAL_REQUIRED = {
    CanaryState.CANARY_REVIEW: {CanaryState.LIVE_APPROVED},
    CanaryState.LIVE_APPROVED: {CanaryState.LIVE},
}


@dataclass
class CanaryRecord:
    candidate_id: str
    state: CanaryState
    symbols: tuple[str, ...] = ()
    max_exposure_pct: float = 0.25
    max_duration_hours: int = 72
    started_at: str | None = None
    why_blocked: str | None = None
    why_promoted: str | None = None
    why_rolled_back: str | None = None
    approval_actor: str | None = None
    approval_timestamp: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    execution_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "state": self.state.value,
            "symbols": list(self.symbols),
            "max_exposure_pct": self.max_exposure_pct,
            "max_duration_hours": self.max_duration_hours,
            "started_at": self.started_at,
            "why_blocked": self.why_blocked,
            "why_promoted": self.why_promoted,
            "why_rolled_back": self.why_rolled_back,
            "approval_actor": self.approval_actor,
            "approval_timestamp": self.approval_timestamp,
            "history": list(self.history),
            "execution_authority": False,
            "auto_promoted": False,
        }


def evaluate_canary_risk(
    *,
    equity: float,
    projected_risk_per_trade: float,
    min_lot: float,
    margin_required: float,
    projected_drawdown_pct: float,
    max_daily_loss_pct: float,
    max_drawdown_pct: float,
    within_portfolio_caps: bool,
    within_correlation_limits: bool,
    execution_safe: bool,
    equity_floor: float = 50.0,
) -> dict[str, Any]:
    reasons: list[str] = []
    if equity < equity_floor:
        reasons.append("equity_below_floor")
    if projected_risk_per_trade <= 0 or min_lot <= 0:
        reasons.append("invalid_sizing")
    if margin_required > equity:
        reasons.append("insufficient_margin")
    if projected_drawdown_pct > max_drawdown_pct:
        reasons.append("projected_drawdown_exceeds_limit")
    if not within_portfolio_caps:
        reasons.append("outside_portfolio_caps")
    if not within_correlation_limits:
        reasons.append("outside_correlation_limits")
    if not execution_safe:
        reasons.append("execution_not_safe")
    # Never increase risk to make canary testable
    if reasons:
        return {
            "result": "CANARY_BLOCKED",
            "why_blocked": ",".join(reasons),
            "risk_increased_to_test": False,
            "max_daily_loss_pct": max_daily_loss_pct,
        }
    return {
        "result": "CANARY_ELIGIBLE",
        "why_blocked": None,
        "risk_increased_to_test": False,
        "max_daily_loss_pct": max_daily_loss_pct,
    }


@dataclass
class CanaryStore:
    records: dict[str, CanaryRecord] = field(default_factory=dict)
    auto_promote_to_live: bool = False
    _lock: RLock = field(default_factory=RLock, repr=False)

    def start(
        self,
        *,
        candidate_id: str,
        symbols: list[str] | tuple[str, ...] | None = None,
        max_exposure_pct: float = 0.25,
        max_duration_hours: int = 72,
    ) -> CanaryRecord:
        rec = CanaryRecord(
            candidate_id=str(candidate_id or uuid4()),
            state=CanaryState.SHADOW,
            symbols=tuple(symbols or ()),
            max_exposure_pct=float(max_exposure_pct),
            max_duration_hours=int(max_duration_hours),
            history=[{"to": CanaryState.SHADOW.value, "at": datetime.now(UTC).isoformat()}],
        )
        with self._lock:
            self.records[rec.candidate_id] = rec
        return rec

    def transition(
        self,
        candidate_id: str,
        target: CanaryState,
        *,
        actor: str | None = None,
        note: str | None = None,
        why_blocked: str | None = None,
        why_promoted: str | None = None,
        why_rolled_back: str | None = None,
    ) -> CanaryRecord:
        with self._lock:
            rec = self.records[candidate_id]
            allowed = set(_AUTO.get(rec.state, set())) | set(
                _APPROVAL_REQUIRED.get(rec.state, set())
            )
            if target not in allowed:
                raise ValueError(f"illegal transition {rec.state} → {target}")
            if target in _APPROVAL_REQUIRED.get(rec.state, set()):
                if not actor or actor in {"system", "auto", ""}:
                    raise PermissionError(
                        "LIVE_APPROVED / LIVE requires explicit approval actor"
                    )
                if self.auto_promote_to_live:
                    raise PermissionError("auto_promote_to_live is forbidden")
            # LIVE never grants execution_authority in this governance plane —
            # actual live path requires authorized production deployment.
            rec.state = target
            rec.execution_authority = False
            if why_blocked:
                rec.why_blocked = why_blocked
            if why_promoted:
                rec.why_promoted = why_promoted
            if why_rolled_back:
                rec.why_rolled_back = why_rolled_back
            if actor:
                rec.approval_actor = actor
                rec.approval_timestamp = datetime.now(UTC).isoformat()
            if target is CanaryState.CANARY and not rec.started_at:
                rec.started_at = datetime.now(UTC).isoformat()
            rec.history.append(
                {
                    "to": target.value,
                    "at": datetime.now(UTC).isoformat(),
                    "actor": actor,
                    "note": note,
                }
            )
            return rec

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [r.to_dict() for r in self.records.values()]
        return {
            "count": len(rows),
            "auto_promote_to_live": False,
            "records": rows[-20:],
        }
