"""Phase 5.1 eligibility matrix A–H (isolated, LIVE off)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
    evaluate_account_eligibility,
)
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ConflictError
from app.domain.multi_account.effective_risk import RiskSettingProposal
from app.domain.multi_account.ownership_claim import InMemoryOwnershipClaimRegistry
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
    CentralSignalIntent,
)

pytestmark = [pytest.mark.unit]

_SETTINGS_OFF = SimpleNamespace(
    multi_account_dispatch_enabled=False,
    multi_account_live_submit_enabled=False,
)


def _intent(user_id, account_id) -> AccountExecutionIntent:
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4010"),
    )
    return AccountExecutionIntent.for_account(
        signal=signal,
        user_id=user_id,
        broker_account_id=account_id,
    )


def _ok_proposal() -> RiskSettingProposal:
    return RiskSettingProposal(
        planned_risk_pct=Decimal("10"),
        aggregate_open_risk_pct=Decimal("30"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )


def test_case_ownership_unverified_blocked() -> None:
    user = uuid4()
    _u, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        proposal=_ok_proposal(),
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=False, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
        require_readiness=True,
    )
    assert evaluation.state is AccountExecutionState.BLOCKED
    assert evaluation.block_reason == "ownership_unverified"


def test_case_a_eligible_with_readiness() -> None:
    user = uuid4()
    account = uuid4()
    updated, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, account),
        proposal=_ok_proposal(),
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True, heartbeat_stale=False),
        require_readiness=True,
    )
    assert updated.state is AccountExecutionState.ELIGIBLE
    assert evaluation.dry_run is True
    assert evaluation.readiness_scope == "prefs_account_worker"


def test_case_b_risk_preference_blocked() -> None:
    user = uuid4()
    _u, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("1.00"),
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        ),
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
        require_readiness=True,
    )
    assert evaluation.state is AccountExecutionState.BLOCKED
    assert evaluation.block_reason


def test_case_c_inactive_account_blocked() -> None:
    user = uuid4()
    _u, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        proposal=_ok_proposal(),
        settings=_SETTINGS_OFF,
        account=AccountReadiness(status="revoked", user_id=user),
        worker=WorkerReadiness(present=True, ready=True),
        require_readiness=True,
    )
    assert evaluation.state is AccountExecutionState.BLOCKED
    assert "revoked" in (evaluation.block_reason or "")


def test_case_d_worker_unavailable_blocked() -> None:
    user = uuid4()
    _u, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        proposal=_ok_proposal(),
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=False, ready=False),
        require_readiness=True,
    )
    assert evaluation.block_reason == "worker_missing"

    _u2, evaluation2 = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        proposal=_ok_proposal(),
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True, heartbeat_stale=True),
        require_readiness=True,
    )
    assert evaluation2.block_reason == "worker_heartbeat_stale"


def test_case_e_foreign_user_denied() -> None:
    owner = uuid4()
    stranger = uuid4()
    with pytest.raises(AuthorizationError):
        evaluate_account_eligibility(
            actor_user_id=stranger,
            intent=_intent(owner, uuid4()),
            proposal=_ok_proposal(),
            settings=_SETTINGS_OFF,
            account=AccountReadiness(status="active", user_id=owner),
            worker=WorkerReadiness(present=True, ready=True),
            require_readiness=True,
        )


def test_case_f_missing_preferences_fail_closed() -> None:
    user = uuid4()

    def boom(_uid):
        raise RuntimeError("db_down")

    _u, evaluation = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        load_preferences=boom,
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
        require_readiness=True,
    )
    assert evaluation.state is AccountExecutionState.BLOCKED
    assert "preference_storage_unavailable" in (evaluation.block_reason or "")

    _u2, evaluation2 = evaluate_account_eligibility(
        actor_user_id=user,
        intent=_intent(user, uuid4()),
        load_preferences=lambda _u: {},
        settings=_SETTINGS_OFF,
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
        require_readiness=True,
    )
    assert evaluation2.state is AccountExecutionState.BLOCKED


def test_case_g_duplicate_active_account_claim_rejected() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    user = uuid4()
    registry.register_claim(
        user_id=user, broker_id=uuid4(), login="1001", server="Weltrade-Real"
    )
    with pytest.raises(ConflictError, match="already has an active MT5"):
        registry.register_claim(
            user_id=user, broker_id=uuid4(), login="1002", server="Weltrade-Real"
        )


def test_case_h_concurrent_users_no_cross_leak() -> None:
    def run_one(_i: int):
        user = uuid4()
        account = uuid4()
        updated, evaluation = evaluate_account_eligibility(
            actor_user_id=user,
            intent=_intent(user, account),
            proposal=_ok_proposal(),
            settings=_SETTINGS_OFF,
            account=AccountReadiness(
                status="active", ownership_verified=True, user_id=user
            ),
            worker=WorkerReadiness(present=True, ready=True),
            require_readiness=True,
        )
        return (
            str(user),
            str(account),
            str(updated.user_id),
            str(updated.broker_account_id),
            evaluation.state.value,
            evaluation.effective.get("planned_risk_pct"),
        )

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(run_one, i) for i in range(24)]
        for fut in as_completed(futures):
            results.append(fut.result())

    assert len(results) == 24
    user_ids = {r[0] for r in results}
    assert len(user_ids) == 24
    for user, account, out_user, out_account, state, planned in results:
        assert user == out_user
        assert account == out_account
        assert state == "eligible"
        assert planned == "10"
