"""Bounded adaptive strategy proposals — never increase risk ceilings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any
from uuid import uuid4

_RISK_KEYS = frozenset(
    {
        "planned_risk_pct",
        "max_lot",
        "aggregate_open_risk_pct",
        "daily_loss_pct",
        "max_concurrent_positions",
        "risk_pct",
        "lot",
        "volume",
    }
)


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@dataclass(frozen=True, slots=True)
class AdaptiveProposal:
    proposal_id: str
    strategy_id: str
    created_at: datetime
    rationale: str
    current_params: dict[str, Any]
    proposed_params: dict[str, Any]
    accepted: bool
    reject_reason: str | None
    status: str  # proposed | approved | applied | rolled_back | rejected
    regime: str | None = None


@dataclass
class AdaptiveProposalStore:
    _items: list[AdaptiveProposal] = field(default_factory=list)
    _validated: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _min_interval_seconds: int = 300
    _last_propose_at: dict[str, datetime] = field(default_factory=dict)

    def propose(
        self,
        *,
        strategy_id: str,
        current_params: dict[str, Any],
        proposed_params: dict[str, Any],
        rationale: str,
        regime: str | None = None,
        now: datetime | None = None,
    ) -> AdaptiveProposal:
        clock = now or datetime.now(UTC)
        with self._lock:
            last = self._last_propose_at.get(strategy_id)
            if last and (clock - last).total_seconds() < self._min_interval_seconds:
                p = AdaptiveProposal(
                    proposal_id=str(uuid4()),
                    strategy_id=strategy_id,
                    created_at=clock,
                    rationale=rationale,
                    current_params=dict(current_params),
                    proposed_params=dict(proposed_params),
                    accepted=False,
                    reject_reason="rate_limited",
                    status="rejected",
                    regime=regime,
                )
                self._items.append(p)
                return p

            ok, reason = _risk_tighten_only(current_params, proposed_params)
            if not ok:
                p = AdaptiveProposal(
                    proposal_id=str(uuid4()),
                    strategy_id=strategy_id,
                    created_at=clock,
                    rationale=rationale,
                    current_params=dict(current_params),
                    proposed_params=dict(proposed_params),
                    accepted=False,
                    reject_reason=reason,
                    status="rejected",
                    regime=regime,
                )
                self._items.append(p)
                return p

            # Snapshot validated baseline on first successful propose
            self._validated.setdefault(strategy_id, dict(current_params))
            self._last_propose_at[strategy_id] = clock
            p = AdaptiveProposal(
                proposal_id=str(uuid4()),
                strategy_id=strategy_id,
                created_at=clock,
                rationale=rationale,
                current_params=dict(current_params),
                proposed_params=dict(proposed_params),
                accepted=True,
                reject_reason=None,
                status="proposed",
                regime=regime,
            )
            self._items.append(p)
            return p

    def approve(self, proposal_id: str) -> AdaptiveProposal | None:
        with self._lock:
            for i, p in enumerate(self._items):
                if p.proposal_id == proposal_id and p.status == "proposed":
                    updated = AdaptiveProposal(
                        proposal_id=p.proposal_id,
                        strategy_id=p.strategy_id,
                        created_at=p.created_at,
                        rationale=p.rationale,
                        current_params=p.current_params,
                        proposed_params=p.proposed_params,
                        accepted=True,
                        reject_reason=None,
                        status="approved",
                        regime=p.regime,
                    )
                    self._items[i] = updated
                    return updated
        return None

    def apply_approved(self, proposal_id: str) -> AdaptiveProposal | None:
        """Mark approved proposal applied — caller must not LIVE-deploy."""
        with self._lock:
            for i, p in enumerate(self._items):
                if p.proposal_id == proposal_id and p.status == "approved":
                    updated = AdaptiveProposal(
                        proposal_id=p.proposal_id,
                        strategy_id=p.strategy_id,
                        created_at=p.created_at,
                        rationale=p.rationale,
                        current_params=p.current_params,
                        proposed_params=p.proposed_params,
                        accepted=True,
                        reject_reason=None,
                        status="applied",
                        regime=p.regime,
                    )
                    self._items[i] = updated
                    return updated
        return None

    def rollback(self, strategy_id: str) -> dict[str, Any] | None:
        with self._lock:
            baseline = self._validated.get(strategy_id)
            if baseline is None:
                return None
            clock = datetime.now(UTC)
            self._items.append(
                AdaptiveProposal(
                    proposal_id=str(uuid4()),
                    strategy_id=strategy_id,
                    created_at=clock,
                    rationale="rollback_to_validated",
                    current_params={},
                    proposed_params=dict(baseline),
                    accepted=True,
                    reject_reason=None,
                    status="rolled_back",
                    regime=None,
                )
            )
            return dict(baseline)

    def list_for(self, strategy_id: str | None = None) -> list[AdaptiveProposal]:
        with self._lock:
            if strategy_id is None:
                return list(self._items)
            return [p for p in self._items if p.strategy_id == strategy_id]


def _risk_tighten_only(
    current: dict[str, Any],
    proposed: dict[str, Any],
) -> tuple[bool, str | None]:
    for key, new_val in proposed.items():
        if key not in _RISK_KEYS:
            continue
        old = _dec(current.get(key))
        new = _dec(new_val)
        if old is None or new is None:
            continue
        # Higher risk ceiling = loosen — reject
        if new > old:
            return False, f"risk_increase_forbidden:{key}"
    return True, None


def propose_adaptation(
    *,
    strategy_id: str,
    current_params: dict[str, Any],
    proposed_params: dict[str, Any],
    rationale: str,
    regime: str | None = None,
    store: AdaptiveProposalStore | None = None,
) -> AdaptiveProposal:
    return (store or get_adaptive_store()).propose(
        strategy_id=strategy_id,
        current_params=current_params,
        proposed_params=proposed_params,
        rationale=rationale,
        regime=regime,
    )


_STORE = AdaptiveProposalStore()


def get_adaptive_store() -> AdaptiveProposalStore:
    return _STORE
