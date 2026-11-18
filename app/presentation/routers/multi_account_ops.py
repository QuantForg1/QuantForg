"""Phase 7/11 — multi-account dispatch observability + Owner kill-switch."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services.multi_account_dispatch_dry_run import DispatchTarget
from app.application.services.multi_account_dispatch_queue import (
    get_durable_dispatch_queue,
)
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.application.services.multi_account_ops_service import (
    customer_dispatch_status,
    owner_ops_snapshot,
)
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.identity.designated_owner import is_designated_owner_email
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)
from app.presentation.dependencies.auth import CurrentUser, require_roles
from core.config.settings import AppEnvironment, get_settings

router = APIRouter(prefix="/multi-account", tags=["multi-account-ops"])

OwnerUser = Annotated[AuthUserDTO, Depends(require_roles(UserRole.OWNER))]


class UserKillSwitchRequest(BaseModel):
    user_id: UUID
    enabled: bool
    reason: str = Field(min_length=3, max_length=500)


class StagingEligibilityProbeRequest(BaseModel):
    """Staging-only non-executing eligibility/risk-ceiling probe."""

    user_id: UUID
    broker_account_id: UUID
    mode: str = Field(
        default="baseline",
        description="baseline | risk_ceiling",
        max_length=32,
    )
    idempotency_key: str = Field(default="", max_length=120)


def _require_designated_owner(user: AuthUserDTO) -> None:
    if not is_designated_owner_email(getattr(user, "email", "")):
        raise AuthorizationError(
            "Designated owner required",
            code="designated_owner_required",
        )


def _require_staging_mutate() -> None:
    """Per-user kill-switch mutation is staging-safe only for Phase 11 proofs.

    Never flips Production DISPATCH / LIVE_SUBMIT feature flags.
    """
    settings = get_settings()
    if settings.app_env == AppEnvironment.PRODUCTION:
        raise AuthorizationError(
            "Per-user dispatch kill-switch mutation is disabled in production "
            "for this Phase 11 surface",
            code="production_user_kill_switch_disabled",
        )


@router.get("/dispatch/status")
async def my_dispatch_status(user: CurrentUser) -> dict[str, Any]:
    return customer_dispatch_status(user_id=UUID(str(user.id)))


@router.get("/ops/summary")
async def owner_multi_account_ops(user: OwnerUser) -> dict[str, Any]:
    _require_designated_owner(user)
    worker_summary: dict[str, Any] = {}
    try:
        from datetime import timedelta

        from app.application.services.mt5_worker_api import Mt5WorkerApiFacade
        from app.application.services.mt5_worker_control_plane import (
            Mt5WorkerControlPlane,
        )

        settings = get_settings()
        token = ""
        secret = getattr(settings, "worker_service_token", None)
        if secret is not None:
            token = secret.get_secret_value().strip()
        plane = Mt5WorkerControlPlane(service_token=token or "unconfigured")
        facade = Mt5WorkerApiFacade(
            plane=plane,
            stale_after=timedelta(
                seconds=int(getattr(settings, "worker_heartbeat_stale_seconds", 90))
            ),
        )
        worker_summary = {
            "worker_count": facade.ops_summary().get("worker_count"),
            "credentials_exposed": False,
        }
    except Exception:
        worker_summary = {"worker_count": None, "unavailable": True}
    return owner_ops_snapshot(worker_summary=worker_summary)


@router.post("/ops/user-kill-switch")
async def set_user_dispatch_kill_switch(
    body: UserKillSwitchRequest,
    user: OwnerUser,
) -> dict[str, Any]:
    """Owner-only per-user dispatch kill switch (staging mutate).

    Isolates one user from new dispatch enqueue/claim. Does not arm global ITE
    kill-switch, does not change feature flags, and does not alter open
    positions / PME / OMS / Weltrade LIVE.
    """
    _require_designated_owner(user)
    _require_staging_mutate()
    queue = get_durable_dispatch_queue()
    result = queue.set_kill_switch(
        user_id=body.user_id,
        enabled=bool(body.enabled),
        actor_user_id=UUID(str(user.id)),
        reason=body.reason,
    )
    return {
        **result,
        "actor_email_domain": "designated_owner",
        "credentials_exposed": False,
        "feature_flags_unchanged": True,
        "orders_submitted": 0,
    }


@router.get("/ops/user-kill-switch/{user_id}")
async def get_user_dispatch_kill_switch(
    user_id: UUID,
    user: OwnerUser,
) -> dict[str, Any]:
    _require_designated_owner(user)
    queue = get_durable_dispatch_queue()
    enabled = queue.is_user_kill_switched(user_id)
    return {
        "ok": True,
        "user_id": str(user_id),
        "enabled": enabled,
        "live_submit_allowed": False,
        "positions_unaffected": True,
        "credentials_exposed": False,
    }


@router.get("/ops/user-kill-switch-audit")
async def list_user_dispatch_kill_switch_audit(
    user: OwnerUser,
    limit: int = 50,
) -> dict[str, Any]:
    _require_designated_owner(user)
    queue = get_durable_dispatch_queue()
    rows = queue.kill_switch_audit(limit=min(max(limit, 1), 100))
    return {
        "ok": True,
        "events": rows,
        "credentials_exposed": False,
        "live_submit_allowed": False,
    }


@router.post("/ops/staging-eligibility-probe")
async def staging_eligibility_probe(
    body: StagingEligibilityProbeRequest,
    user: OwnerUser,
) -> dict[str, Any]:
    """Staging-only: prove baseline vs risk-ceiling block without order_send."""
    _require_designated_owner(user)
    _require_staging_mutate()
    mode = (body.mode or "baseline").strip().lower()
    if mode not in {"baseline", "risk_ceiling"}:
        return {"ok": False, "error": "invalid_mode", "live_submit_allowed": False}

    if mode == "risk_ceiling":
        proposal = RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("9.00"),  # exceeds the 5.00 system lot bound
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        )
    else:
        proposal = RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("0.01"),
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        )

    target = DispatchTarget(
        user_id=body.user_id,
        broker_account_id=body.broker_account_id,
        proposal=proposal,
        account=AccountReadiness(
            status="active",
            ownership_verified=True,
            user_id=body.user_id,
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    key = (body.idempotency_key or "").strip() or (
        f"e12-probe:{mode}:{body.user_id}:{body.broker_account_id}"
    )
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
        idempotency_key=key,
        metadata={
            "staging_eligibility_probe": True,
            "mode": mode,
            "delivery_suppressed": True,
            "live_submit_allowed": False,
        },
    )
    from types import SimpleNamespace

    lab_settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=False,
    )
    queue = get_durable_dispatch_queue()
    if queue.is_user_kill_switched(body.user_id):
        return {
            "ok": True,
            "mode": mode,
            "blocked": True,
            "block_reason": "user_kill_switch",
            "job_count": 0,
            "live_submit_allowed": False,
            "orders_submitted": 0,
            "positions_unaffected": True,
        }
    _plan, jobs = queue.plan_and_enqueue(
        signal=signal,
        targets=[target],
        settings=lab_settings,
    )
    job = jobs[0] if jobs else None
    blocked = bool(job is not None and job.state is AccountExecutionState.BLOCKED)
    return {
        "ok": True,
        "mode": mode,
        "blocked": blocked,
        "block_reason": (job.block_reason if job else None),
        "state": (job.state.value if job else None),
        "job_count": len(jobs),
        "kill_switch": bool(job.kill_switch) if job else False,
        "live_submit_allowed": False,
        "orders_submitted": 0,
        "positions_unaffected": True,
        "credentials_exposed": False,
    }
