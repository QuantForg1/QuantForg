"""Phase 5 / 5.1 — preference-aware multi-account eligibility (dry-run safe).

Connects Phase 4 ``user_risk_settings`` / ``resolve_effective_risk`` to the
Phase 1 account-execution intent vocabulary, with optional account/worker
readiness gates for the Phase 5.1 acceptance matrix.

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

_INACTIVE_ACCOUNT_STATUSES = frozenset({"revoked", "inactive", "disabled", "closed"})


@dataclass(frozen=True, slots=True)
class AccountReadiness:
    """Caller-supplied broker account readiness (never invents DB truth)."""

    status: str
    ownership_verified: bool = False
    user_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class WorkerReadiness:
    """Caller-supplied worker readiness (heartbeat ≠ broker auth)."""

    present: bool
    ready: bool
    heartbeat_stale: bool = False
    trade_allowed: bool | None = None
    detail: str = ""


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
    readiness_scope: str = "prefs_only"

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
            "readiness_scope": self.readiness_scope,
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


def _blocked(
    *,
    intent: AccountExecutionIntent,
    reason: str,
    effective: dict[str, Any],
    dispatch_ok: bool,
    live_ok: bool,
    dry_run: bool,
    source: str,
    readiness_scope: str,
) -> tuple[AccountExecutionIntent, EligibilityEvaluation]:
    evaluation = EligibilityEvaluation(
        user_id=intent.user_id,
        broker_account_id=intent.broker_account_id,
        state=AccountExecutionState.BLOCKED,
        block_reason=reason,
        effective=effective,
        dispatch_allowed=dispatch_ok,
        live_submit_allowed=live_ok,
        dry_run=dry_run,
        source=source,
        readiness_scope=readiness_scope,
    )
    updated = intent.transition(
        AccountExecutionState.BLOCKED,
        block_reason=reason,
    )
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


def evaluate_account_eligibility(
    *,
    actor_user_id: UUID,
    intent: AccountExecutionIntent,
    proposal: RiskSettingProposal | None = None,
    load_preferences: PrefLoader | None = None,
    settings: Any | None = None,
    account: AccountReadiness | None = None,
    worker: WorkerReadiness | None = None,
    require_readiness: bool = False,
) -> tuple[AccountExecutionIntent, EligibilityEvaluation]:
    """Resolve prefs (+ optional readiness) → ELIGIBLE/BLOCKED.

    Raises ``AuthorizationError`` when ``actor_user_id`` does not own the intent.
    Never submits orders. Never enables LIVE gates.
    """
    assert_own_user(actor_user_id, intent.user_id)

    dispatch_ok = multi_account_dispatch_allowed(settings)
    live_ok = multi_account_live_submit_allowed(settings)
    dry_run = not dispatch_ok
    readiness_scope = (
        "prefs_account_worker"
        if (account is not None or worker is not None or require_readiness)
        else "prefs_only"
    )

    if require_readiness and (account is None or worker is None):
        return _blocked(
            intent=intent,
            reason="readiness_context_required",
            effective={},
            dispatch_ok=dispatch_ok,
            live_ok=live_ok,
            dry_run=dry_run,
            source="none",
            readiness_scope=readiness_scope,
        )

    if account is not None:
        if account.user_id is not None and account.user_id != intent.user_id:
            return _blocked(
                intent=intent,
                reason="account_user_mismatch",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="account",
                readiness_scope=readiness_scope,
            )
        status = (account.status or "").strip().lower()
        if status in _INACTIVE_ACCOUNT_STATUSES or status == "":
            return _blocked(
                intent=intent,
                reason=f"account_status_{status or 'unknown'}",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="account",
                readiness_scope=readiness_scope,
            )
        # pending is allowed only for prefs-only probes; full readiness
        # requires active.
        allow_pending = status == "pending" and not require_readiness
        if status != "active" and not allow_pending:
            return _blocked(
                intent=intent,
                reason=f"account_not_active:{status}",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="account",
                readiness_scope=readiness_scope,
            )
        # Full readiness path requires verified ownership evidence.
        if require_readiness and not account.ownership_verified:
            return _blocked(
                intent=intent,
                reason="ownership_unverified",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="account",
                readiness_scope=readiness_scope,
            )

    if worker is not None:
        if not worker.present:
            return _blocked(
                intent=intent,
                reason="worker_missing",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="worker",
                readiness_scope=readiness_scope,
            )
        if worker.heartbeat_stale:
            return _blocked(
                intent=intent,
                reason="worker_heartbeat_stale",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="worker",
                readiness_scope=readiness_scope,
            )
        if not worker.ready:
            return _blocked(
                intent=intent,
                reason=worker.detail or "worker_not_ready",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="worker",
                readiness_scope=readiness_scope,
            )
        if worker.trade_allowed is False:
            return _blocked(
                intent=intent,
                reason="worker_trade_not_allowed",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="worker",
                readiness_scope=readiness_scope,
            )

    source = "proposal"
    resolved_proposal = proposal
    if resolved_proposal is None:
        if load_preferences is None:
            from app.application.services.user_risk_preferences_service import (
                get_user_risk_preferences,
            )

            load_preferences = get_user_risk_preferences
        try:
            payload = load_preferences(intent.user_id)
        except Exception as exc:
            return _blocked(
                intent=intent,
                reason=f"preference_storage_unavailable:{type(exc).__name__}",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="storage_error",
                readiness_scope=readiness_scope,
            )
        if not isinstance(payload, dict) or not payload:
            return _blocked(
                intent=intent,
                reason="preference_payload_untrusted",
                effective={},
                dispatch_ok=dispatch_ok,
                live_ok=live_ok,
                dry_run=dry_run,
                source="untrusted",
                readiness_scope=readiness_scope,
            )
        source = str(payload.get("source") or "default_copy")
        resolved_proposal = _proposal_from_preferences_payload(payload)

    effective: EffectiveRiskProfile = resolve_effective_risk(resolved_proposal)
    if not effective.ok:
        return _blocked(
            intent=intent,
            reason=effective.block_reason or "effective_risk_rejected",
            effective=effective.to_dict(),
            dispatch_ok=dispatch_ok,
            live_ok=live_ok,
            dry_run=dry_run,
            source=source,
            readiness_scope=readiness_scope,
        )

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
        readiness_scope=readiness_scope,
    )
    planned = effective.max_lot
    updated = intent.transition(
        AccountExecutionState.ELIGIBLE,
        planned_volume=planned,
        block_reason=None,
    )
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
