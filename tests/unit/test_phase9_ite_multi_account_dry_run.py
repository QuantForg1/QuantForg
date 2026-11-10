"""Phase 9 — ITE multi-account dry-run adapter (non-executing)."""

from __future__ import annotations

import inspect
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.ite_multi_account_dry_run import (
    attach_ite_multi_account_dry_run,
    build_central_signal_from_ite_decision,
    reset_ite_dry_run_state_for_tests,
    run_ite_multi_account_dry_run,
    set_ite_dry_run_target_provider,
)
from app.application.services.multi_account_dispatch_dry_run import DispatchTarget
from app.application.services.multi_account_dispatch_queue import (
    DurableDispatchQueue,
    reset_durable_dispatch_queue_for_tests,
)
from app.application.services.multi_account_eligibility_service import (
    AccountReadiness,
    WorkerReadiness,
)
from app.domain.multi_account.effective_risk import RiskSettingProposal

pytestmark = [pytest.mark.unit]

_SETTINGS_OFF = SimpleNamespace(
    multi_account_dispatch_enabled=False,
    multi_account_live_submit_enabled=False,
)
_SETTINGS_LIVE_ARMED = SimpleNamespace(
    multi_account_dispatch_enabled=True,
    multi_account_live_submit_enabled=True,
)


def _proposal() -> RiskSettingProposal:
    return RiskSettingProposal(
        planned_risk_pct=Decimal("10"),
        aggregate_open_risk_pct=Decimal("30"),
        max_lot=Decimal("0.01"),
        daily_loss_pct=Decimal("48"),
        max_concurrent_positions=1,
    )


def _decision(**kwargs: object) -> SimpleNamespace:
    base = {
        "id": "dec-phase9-1",
        "symbol": "XAUUSD",
        "action": SimpleNamespace(value="BUY"),
        "quality": 80,
        "entry": Decimal("4000"),
        "stop_loss": Decimal("3990"),
        "take_profit": Decimal("4010"),
        "eligibility": SimpleNamespace(eligible=True, rejection_reasons=[]),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _ready_target(user=None, account=None, **kwargs: object) -> DispatchTarget:
    user = user or uuid4()
    account = account or uuid4()
    return DispatchTarget(
        user_id=user,
        broker_account_id=account,
        proposal=_proposal(),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
        **kwargs,
    )


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_ite_dry_run_state_for_tests()
    reset_durable_dispatch_queue_for_tests()
    yield
    reset_ite_dry_run_state_for_tests()
    reset_durable_dispatch_queue_for_tests()


def test_invalid_ite_signal_rejected() -> None:
    result = run_ite_multi_account_dry_run(
        decision=_decision(action=SimpleNamespace(value="NO_TRADE")),
        trace_id="t1",
        targets=[_ready_target()],
        settings=_SETTINGS_OFF,
    )
    assert result["ok"] is False
    assert result["error"] == "invalid_ite_signal"
    assert result["order_send"] is False


def test_duplicate_signal_idempotent() -> None:
    user, account = uuid4(), uuid4()
    target = _ready_target(user, account)
    decision = _decision(id="same-dec")
    first = run_ite_multi_account_dry_run(
        decision=decision,
        trace_id="t1",
        targets=[target],
        settings=_SETTINGS_OFF,
    )
    second = run_ite_multi_account_dry_run(
        decision=decision,
        trace_id="t1",
        targets=[target],
        settings=_SETTINGS_OFF,
    )
    assert first["ok"] and second["ok"]
    assert first["signal_idempotency_key"] == second["signal_idempotency_key"]
    assert first["job_count"] == 1
    assert second["job_count"] == 1  # idempotent enqueue returns existing


def test_no_eligible_accounts() -> None:
    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t1",
        targets=[],
        settings=_SETTINGS_OFF,
    )
    assert result["ok"] is True
    assert result["detail"] == "no_eligible_targets"
    assert result["job_count"] == 0


def test_one_eligible_one_blocked_and_isolation() -> None:
    good_user, good_acct = uuid4(), uuid4()
    bad_user, bad_acct = uuid4(), uuid4()
    targets = [
        _ready_target(good_user, good_acct),
        DispatchTarget(
            user_id=bad_user,
            broker_account_id=bad_acct,
            proposal=_proposal(),
            account=AccountReadiness(
                status="active", ownership_verified=False, user_id=bad_user
            ),
            worker=WorkerReadiness(present=True, ready=True),
        ),
    ]
    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-mix",
        targets=targets,
        settings=_SETTINGS_OFF,
    )
    assert result["ok"] is True
    assert result["eligible"] == 1
    assert result["blocked"] == 1
    blocked = next(i for i in result["items"] if i["state"] == "blocked")
    assert blocked["block_reason"] == "ownership_unverified"
    assert blocked["user_id"] == str(bad_user)
    # Good user not contaminated by bad user block.
    good = next(i for i in result["items"] if i["user_id"] == str(good_user))
    assert good["state"] in {"eligible", "queued"}


def test_foreign_account_blocked() -> None:
    owner = uuid4()
    stranger = uuid4()
    target = DispatchTarget(
        user_id=owner,
        broker_account_id=uuid4(),
        actor_user_id=stranger,
        proposal=_proposal(),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=owner
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-foreign",
        targets=[target],
        settings=_SETTINGS_OFF,
    )
    assert result["blocked"] == 1
    assert result["items"][0]["state"] == "blocked"


def test_stale_worker_blocked() -> None:
    user = uuid4()
    target = DispatchTarget(
        user_id=user,
        broker_account_id=uuid4(),
        proposal=_proposal(),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True, heartbeat_stale=True),
    )
    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-stale",
        targets=[target],
        settings=_SETTINGS_OFF,
    )
    assert result["items"][0]["block_reason"] == "worker_heartbeat_stale"


def test_global_risk_ceiling_violation() -> None:
    user = uuid4()
    target = DispatchTarget(
        user_id=user,
        broker_account_id=uuid4(),
        proposal=RiskSettingProposal(
            planned_risk_pct=Decimal("10"),
            aggregate_open_risk_pct=Decimal("30"),
            max_lot=Decimal("5.00"),  # above global ceiling
            daily_loss_pct=Decimal("48"),
            max_concurrent_positions=1,
        ),
        account=AccountReadiness(
            status="active", ownership_verified=True, user_id=user
        ),
        worker=WorkerReadiness(present=True, ready=True),
    )
    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-risk",
        targets=[target],
        settings=_SETTINGS_OFF,
    )
    assert result["blocked"] == 1
    assert result["items"][0]["state"] == "blocked"


def test_live_submit_armed_refused() -> None:
    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-live",
        targets=[_ready_target()],
        settings=_SETTINGS_LIVE_ARMED,
    )
    assert result["ok"] is False
    assert result["error"] == "live_submit_armed_refused"
    assert result["live_submit_allowed"] is False


def test_queue_outage_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomQueue(DurableDispatchQueue):
        def plan_and_enqueue(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("db_down")

    result = run_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-outage",
        targets=[_ready_target()],
        settings=_SETTINGS_OFF,
        queue=BoomQueue(),
    )
    assert result["ok"] is False
    assert "queue_outage" in (result.get("error") or "")


def test_attach_merges_diagnostics_without_raising() -> None:
    set_ite_dry_run_target_provider(lambda: [_ready_target()])
    diag = attach_ite_multi_account_dry_run(
        decision=_decision(),
        trace_id="t-attach",
        diagnostics={"existing": True},
        settings=_SETTINGS_OFF,
    )
    assert diag["existing"] is True
    assert diag["multi_account_dry_run"]["ok"] is True
    assert diag["multi_account_dry_run"]["order_send"] is False


def test_adapter_source_has_no_oms_or_order_send() -> None:
    import app.application.services.ite_multi_account_dry_run as mod

    src = inspect.getsource(mod)
    assert "order_send(" not in src
    assert "import gateway_client" not in src
    assert "from app.infrastructure" not in src
    assert "submit_position_plan_batch" not in src


def test_signal_key_stable() -> None:
    signal = build_central_signal_from_ite_decision(
        decision=_decision(id="abc"),
        trace_id="trace-1",
    )
    assert signal is not None
    assert signal.idempotency_key == "ite:abc:XAUUSD:BUY"
    assert signal.metadata.get("live_submit_allowed") is False
