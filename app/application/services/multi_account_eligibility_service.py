"""Phase 5 — preference-aware multi-account eligibility (dry-run safe).

Connects Phase 4 ``user_risk_settings`` / ``resolve_effective_risk`` to the
Phase 1 account-execution intent vocabulary.

LIVE fan-out stays off by default:
- When ``multi_account_dispatch_allowed`` is False, evaluation may still
  classify ELIGIBLE/BLOCKED for inspection, but metadata marks
  ``dispatch_allowed=false`` and callers must not enqueue OMS submits.
- ``multi_account_live_submit_allowed`` is reported only; this module never
  calls order_send / PME / the MT5 gateway.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.services.user_risk_preferences_service import assert_own_user
from app.domain.multi_account.effective_risk import (
    EffectiveRiskProfile,
    RiskSettingProposal,
    resolve_effective_risk,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
)

PrefLoader = Callable[[UUID], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class EligibilityEvaluation:
    """Dry-run eligibility outcome for one account intent."""

    user_id: UUID
    broker_account_id: UUID
    state: AccountExecutionState
    block_reason: str | None
    effective: dict[str, Any]
    dispatch_allowed: bool
    live_submit_allowed: bool
    dry_run: bool
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "broker_account_id": str(self.broker_account_id),
            "state": self.state.value,
            "block_reason": self.block_reason,
            "effective": dict(self.effective),
            "dispatch_allowed": self.dispatch_allowed,
            "live_submit_allowed": self.live_submit_allowed,
            "dry_run": self.dry_run,
            "source": self.source,
        }


def _proposal_from_preferences_payload(payload: dict[str, Any]) -> RiskSettingProposal:
    raw_prefs = payload.get("preferences")
    prefs = raw_prefs if isinstance(raw_prefs, dict) else payload
    if not isinstance(prefs, dict):
        return RiskSettingProposal()
    conc = prefs.get("max_concurrent_positions")
    try:
        conc_i = int(conc) if conc is not None and conc != "" else None
    except (TypeError, ValueError):
        conc_i = None
    return RiskSettingProposal(
        planned_risk_pct=_dec(prefs.get("planned_risk_pct")),
        aggregate_open_risk_pct=_dec(prefs.get("aggregate_open_risk_pct")),
        max_lot=_dec(prefs.get("max_lot")),
        daily_loss_pct=_dec(prefs.get("daily_loss_pct")),
        max_concurrent_positions=conc_i,
    )


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def evaluate_account_eligibility(
    *,
    actor_user_id: UUID,
    intent: AccountExecutionIntent,
    proposal: RiskSettingProposal | None = None,
    load_preferences: PrefLoader | None = None,
    settings: Any | None = None,
) -> tuple[AccountExecutionIntent, EligibilityEvaluation]:
    """Resolve prefs → effective risk → ELIGIBLE/BLOCKED transition.

    Raises ``AuthorizationError`` when ``actor_user_id`` does not own the intent.
    Never submits orders. Never enables LIVE gates.
    """
    assert_own_user(actor_user_id, intent.user_id)

    dispatch_ok = multi_account_dispatch_allowed(settings)
    live_ok = multi_account_live_submit_allowed(settings)
    dry_run = not dispatch_ok

    source = "proposal"
    resolved_proposal = proposal
    if resolved_proposal is None:
        if load_preferences is None:
            from app.application.services.user_risk_preferences_service import (
                get_user_risk_preferences,
            )

            load_preferences = get_user_risk_preferences
        payload = load_preferences(intent.user_id)
        source = str(payload.get("source") or "default_copy")
        resolved_proposal = _proposal_from_preferences_payload(payload)

    effective: EffectiveRiskProfile = resolve_effective_risk(resolved_proposal)
    if not effective.ok:
        evaluation = EligibilityEvaluation(
            user_id=intent.user_id,
            broker_account_id=intent.broker_account_id,
            state=AccountExecutionState.BLOCKED,
            block_reason=effective.block_reason or "effective_risk_rejected",
            effective=effective.to_dict(),
            dispatch_allowed=dispatch_ok,
            live_submit_allowed=live_ok,
            dry_run=dry_run,
            source=source,
        )
        updated = intent.transition(
            AccountExecutionState.BLOCKED,
            block_reason=evaluation.block_reason,
        )
        return updated, evaluation

    evaluation = EligibilityEvaluation(
        user_id=intent.user_id,
        broker_account_id=intent.broker_account_id,
        state=AccountExecutionState.ELIGIBLE,
        block_reason=None,
        effective=effective.to_dict(),
        dispatch_allowed=dispatch_ok,
        live_submit_allowed=live_ok,
        dry_run=dry_run,
        source=source,
    )
    # Preference-derived planned volume is advisory only; OMS remains final.
    planned = effective.max_lot
    updated = intent.transition(
        AccountExecutionState.ELIGIBLE,
        planned_volume=planned,
        block_reason=None,
    )
    # Annotate dry-run / gate status without mutating frozen dataclasses' shape
    # beyond metadata copy on a new intent.
    meta = dict(updated.metadata)
    meta["eligibility"] = evaluation.to_dict()
    updated = AccountExecutionIntent(
        execution_id=updated.execution_id,
        signal_id=updated.signal_id,
        user_id=updated.user_id,
        broker_account_id=updated.broker_account_id,
        state=updated.state,
        idempotency_key=updated.idempotency_key,
        block_reason=updated.block_reason,
        planned_volume=updated.planned_volume,
        broker_ticket=updated.broker_ticket,
        attempt_count=updated.attempt_count,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        metadata=meta,
    )
    return updated, evaluation
