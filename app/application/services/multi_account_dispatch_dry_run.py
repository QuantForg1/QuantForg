"""Phase 6 — multi-account dispatch foundation (non-executing).

Plans per-account dispatch from a central signal through eligibility.
Feature gates default OFF. This module never calls OMS, order_send,
PME, or the MT5 gateway — even if dispatch flags were mistakenly True,
``allow_live_submit`` stays False here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID

from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    EligibilityEvaluation,
    WorkerReadiness,
    evaluate_account_eligibility,
)
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
    CentralSignalIntent,
)


@dataclass(frozen=True, slots=True)
class DispatchTarget:
    """One user/account candidate for a central signal."""

    user_id: UUID
    broker_account_id: UUID
    actor_user_id: UUID | None = None
    proposal: RiskSettingProposal | None = None
    account: AccountReadiness | None = None
    worker: WorkerReadiness | None = None


@dataclass(frozen=True, slots=True)
class DispatchPlanItem:
    intent: AccountExecutionIntent
    evaluation: EligibilityEvaluation
    delivery_suppressed: bool
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class DispatchPlan:
    signal_id: UUID
    signal_idempotency_key: str
    dispatch_allowed: bool
    live_submit_allowed: bool
    items: tuple[DispatchPlanItem, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": str(self.signal_id),
            "signal_idempotency_key": self.signal_idempotency_key,
            "dispatch_allowed": self.dispatch_allowed,
            "live_submit_allowed": self.live_submit_allowed,
            "item_count": len(self.items),
            "eligible": sum(
                1
                for i in self.items
                if i.evaluation.state is AccountExecutionState.ELIGIBLE
            ),
            "blocked": sum(
                1
                for i in self.items
                if i.evaluation.state is AccountExecutionState.BLOCKED
            ),
            "delivery_suppressed_all": all(
                i.delivery_suppressed for i in self.items
            ),
        }


class InMemoryDispatchLedger:
    """Idempotent dry-run ledger — process local, no broker I/O."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_key: dict[str, DispatchPlanItem] = {}
        self._plans: list[DispatchPlan] = []

    def get(self, idempotency_key: str) -> DispatchPlanItem | None:
        with self._lock:
            return self._by_key.get(idempotency_key)

    def remember(self, plan: DispatchPlan) -> DispatchPlan:
        with self._lock:
            remembered: list[DispatchPlanItem] = []
            for item in plan.items:
                existing = self._by_key.get(item.idempotency_key)
                if existing is not None:
                    remembered.append(existing)
                    continue
                self._by_key[item.idempotency_key] = item
                remembered.append(item)
            stored = DispatchPlan(
                signal_id=plan.signal_id,
                signal_idempotency_key=plan.signal_idempotency_key,
                dispatch_allowed=plan.dispatch_allowed,
                live_submit_allowed=plan.live_submit_allowed,
                items=tuple(remembered),
                created_at=plan.created_at,
            )
            self._plans.append(stored)
            return stored

    @property
    def plan_count(self) -> int:
        with self._lock:
            return len(self._plans)


def plan_signal_dispatch(
    *,
    signal: CentralSignalIntent,
    targets: list[DispatchTarget],
    settings: Any | None = None,
    require_readiness: bool = True,
    ledger: InMemoryDispatchLedger | None = None,
) -> DispatchPlan:
    """Evaluate each target and build a non-executing dispatch plan.

    Hard rules:
    - Foreign actor vs target.user_id is denied by eligibility.
    - Delivery is always suppressed in this foundation (no OMS/submit).
    - When dispatch flag is off, dry_run remains True on evaluations.
    """
    dispatch_ok = multi_account_dispatch_allowed(settings)
    live_ok = multi_account_live_submit_allowed(settings)
    # Phase 6 foundation: never arm live submit from this module.
    live_ok = False
    items: list[DispatchPlanItem] = []

    for target in targets:
        actor = target.actor_user_id or target.user_id
        intent = AccountExecutionIntent.for_account(
            signal=signal,
            user_id=target.user_id,
            broker_account_id=target.broker_account_id,
        )
        try:
            updated, evaluation = evaluate_account_eligibility(
                actor_user_id=actor,
                intent=intent,
                proposal=target.proposal,
                settings=settings,
                account=target.account,
                worker=target.worker,
                require_readiness=require_readiness,
            )
        except Exception as exc:
            # AuthorizationError and unexpected failures → blocked item, no leak
            blocked = intent.transition(
                AccountExecutionState.BLOCKED,
                block_reason=f"dispatch_plan_denied:{type(exc).__name__}",
            )
            evaluation = EligibilityEvaluation(
                user_id=target.user_id,
                broker_account_id=target.broker_account_id,
                state=AccountExecutionState.BLOCKED,
                block_reason=blocked.block_reason,
                effective={},
                dispatch_allowed=dispatch_ok,
                live_submit_allowed=False,
                dry_run=not dispatch_ok,
                source="dispatch_plan",
                readiness_scope="prefs_account_worker",
            )
            updated = blocked

        # Never advance to SUBMITTING / FILLED here.
        if (
            updated.state is AccountExecutionState.ELIGIBLE
            and dispatch_ok
            and not updated.is_terminal
        ):
            # Queue mark only — delivery still suppressed.
            updated = updated.transition(AccountExecutionState.QUEUED)

        items.append(
            DispatchPlanItem(
                intent=updated,
                evaluation=evaluation,
                delivery_suppressed=True,
                idempotency_key=updated.idempotency_key,
            )
        )

    plan = DispatchPlan(
        signal_id=signal.signal_id,
        signal_idempotency_key=signal.idempotency_key,
        dispatch_allowed=dispatch_ok,
        live_submit_allowed=live_ok,
        items=tuple(items),
    )
    if ledger is not None:
        return ledger.remember(plan)
    return plan
