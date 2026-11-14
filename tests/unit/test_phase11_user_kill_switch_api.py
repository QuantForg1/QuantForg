"""Phase 11 — Owner per-user dispatch kill-switch API (no LIVE / no secrets)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.dto.auth import AuthUserDTO
from app.application.services.multi_account_dispatch_dry_run import DispatchTarget
from app.application.services.multi_account_dispatch_queue import (
    DurableDispatchQueue,
    reset_durable_dispatch_queue_for_tests,
)
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthorizationError
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)
from app.presentation.routers import multi_account_ops as ops_router
from core.config.settings import AppEnvironment

pytestmark = [pytest.mark.unit]


def _owner() -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email=DESIGNATED_OWNER_EMAIL,
        display_name="Owner",
        role=UserRole.OWNER.value,
        status="active",
        auth_user_id=uuid4(),
    )


def _proposal(*, max_lot: str = "0.01") -> RiskSettingProposal:
    return RiskSettingProposal(
        planned_risk_pct=Decimal("10"),
        aggregate_open_risk_pct=Decimal("30"),
        max_lot=Decimal(max_lot),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )


def _ready(user, account, *, max_lot: str = "0.01") -> DispatchTarget:
    return DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=_proposal(max_lot=max_lot),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )


@pytest.fixture(autouse=True)
def _reset_queue() -> None:
    reset_durable_dispatch_queue_for_tests()


@pytest.mark.asyncio
async def test_kill_switch_requires_designated_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ops_router, "is_designated_owner_email", lambda _e: False)
    body = ops_router.UserKillSwitchRequest(
        user_id=uuid4(), enabled=True, reason="phase11 e12"
    )
    with pytest.raises(AuthorizationError) as err:
        await ops_router.set_user_dispatch_kill_switch(body, _owner())
    assert getattr(err.value, "code", "") == "designated_owner_required"


@pytest.mark.asyncio
async def test_kill_switch_refuses_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ops_router,
        "get_settings",
        lambda: SimpleNamespace(app_env=AppEnvironment.PRODUCTION),
    )
    body = ops_router.UserKillSwitchRequest(
        user_id=uuid4(), enabled=True, reason="phase11 e12"
    )
    with pytest.raises(AuthorizationError) as err:
        await ops_router.set_user_dispatch_kill_switch(body, _owner())
    assert getattr(err.value, "code", "") == "production_user_kill_switch_disabled"


@pytest.mark.asyncio
async def test_kill_switch_isolates_user_on_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ops_router,
        "get_settings",
        lambda: SimpleNamespace(app_env=AppEnvironment.STAGING),
    )
    q = DurableDispatchQueue()
    monkeypatch.setattr(ops_router, "get_durable_dispatch_queue", lambda: q)

    u1, a1, u2, a2 = uuid4(), uuid4(), uuid4(), uuid4()
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=False,
    )
    q.plan_and_enqueue(
        signal=CentralSignalIntent.create(
            symbol="XAUUSD", side="BUY", quality=80, idempotency_key="e12:a"
        ),
        targets=[_ready(u1, a1)],
        settings=settings,
    )
    q.plan_and_enqueue(
        signal=CentralSignalIntent.create(
            symbol="XAUUSD", side="BUY", quality=80, idempotency_key="e12:b"
        ),
        targets=[_ready(u2, a2)],
        settings=settings,
    )

    body = ops_router.UserKillSwitchRequest(
        user_id=u1, enabled=True, reason="phase11 e12 isolate A"
    )
    result = await ops_router.set_user_dispatch_kill_switch(body, _owner())
    assert result["ok"] is True
    assert result["enabled"] is True
    assert result["positions_unaffected"] is True
    assert result["global_settings_unchanged"] is True
    assert result["feature_flags_unchanged"] is True
    assert "password" not in str(result).lower()

    assert q.claim_next(worker_id=uuid4(), user_id=u1, broker_account_id=a1) is None
    other = q.claim_next(worker_id=uuid4(), user_id=u2, broker_account_id=a2)
    assert other is not None and other.user_id == u2

    # New enqueue for killed user is blocked at job state.
    _, jobs = q.plan_and_enqueue(
        signal=CentralSignalIntent.create(
            symbol="XAUUSD", side="BUY", quality=80, idempotency_key="e12:a2"
        ),
        targets=[_ready(u1, a1)],
        settings=settings,
    )
    assert jobs[0].state is AccountExecutionState.BLOCKED
    assert jobs[0].block_reason == "user_kill_switch"

    # Restore A
    restore = ops_router.UserKillSwitchRequest(
        user_id=u1, enabled=False, reason="phase11 e12 restore A"
    )
    restored = await ops_router.set_user_dispatch_kill_switch(restore, _owner())
    assert restored["enabled"] is False
    assert q.is_user_kill_switched(u1) is False

    audit = await ops_router.list_user_dispatch_kill_switch_audit(_owner(), limit=10)
    assert audit["ok"] is True
    assert len(audit["events"]) >= 2
    assert audit["events"][-1]["target_user_id"] == str(u1)


@pytest.mark.asyncio
async def test_staging_risk_ceiling_probe_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ops_router,
        "get_settings",
        lambda: SimpleNamespace(app_env=AppEnvironment.STAGING),
    )
    q = DurableDispatchQueue()
    monkeypatch.setattr(ops_router, "get_durable_dispatch_queue", lambda: q)
    user, account = uuid4(), uuid4()
    body = ops_router.StagingEligibilityProbeRequest(
        user_id=user,
        broker_account_id=account,
        mode="risk_ceiling",
        idempotency_key="e12:ceiling",
    )
    out = await ops_router.staging_eligibility_probe(body, _owner())
    assert out["ok"] is True
    assert out["blocked"] is True
    assert out["orders_submitted"] == 0
    assert out["live_submit_allowed"] is False
