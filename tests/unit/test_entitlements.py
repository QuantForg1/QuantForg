"""Trading entitlement: active license or trial; owner/admin exempt."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services import entitlements as ent

pytestmark = [pytest.mark.unit]


def _f(role: str, licensed: bool, trial: bool):
    return lambda *_a: [{"role": role, "licensed": licensed, "trial": trial}]


@pytest.mark.parametrize(
    ("role", "licensed", "trial", "allowed", "reason"),
    [
        ("owner", False, False, True, "platform_operator"),
        ("admin", False, False, True, "platform_operator"),
        ("trader", True, False, True, "license_active"),
        # Free trial discontinued: an active trial row no longer entitles.
        ("trader", False, True, False, "SUBSCRIPTION_INACTIVE"),
        ("trader", False, False, False, "SUBSCRIPTION_INACTIVE"),
    ],
)
def test_matrix(
    role: str, licensed: bool, trial: bool, allowed: bool, reason: str
) -> None:
    out = ent.check_trading_entitlement(
        user_id=uuid4(), fetch=_f(role, licensed, trial)
    )
    assert (out.allowed, out.reason) == (allowed, reason)


def test_unreadable_billing_is_not_entitled() -> None:
    def boom(*_a: object) -> list[object]:
        raise RuntimeError("db")

    out = ent.check_trading_entitlement(user_id=uuid4(), fetch=boom)
    assert not out.allowed and out.reason == "SUBSCRIPTION_UNVERIFIED"


def test_resume_needs_entitlement_but_pause_never(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services import robot_control_service as rc
    from tests.unit.test_robot_control_service import READY, FakeDB

    db = FakeDB()
    monkeypatch.setattr(rc, "_db", lambda: db)
    monkeypatch.setattr(
        ent,
        "check_trading_entitlement",
        lambda **_: ent.Entitlement(False, "SUBSCRIPTION_INACTIVE"),
    )
    u = uuid4()
    a = db.add_account(u, "1001")
    rc.apply_action(user_id=u, broker_account_id=a, action="pause")  # always allowed
    with pytest.raises(rc.RobotControlError) as err:
        rc.apply_action(
            user_id=u, broker_account_id=a, action="resume", readiness_probe=READY
        )
    assert err.value.code == "subscription_required" and err.value.status == 402
    rc.apply_action(user_id=u, broker_account_id=a, action="emergency_stop", reason="x")


def test_worker_entry_rejected_without_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.application.services.multi_account_oms_execution import (
        authorize_worker_execution,
    )
    from tests.unit.test_multi_account_owner_guard import (
        BUY,
        CAPS,
        NOW,
        SETTINGS,
        _snap,
        _worker,
    )

    monkeypatch.setattr(
        ent,
        "check_trading_entitlement",
        lambda **_: ent.Entitlement(False, "SUBSCRIPTION_INACTIVE"),
    )
    w = _worker()
    auth = authorize_worker_execution(
        worker=w,
        intent_id=uuid4(),
        job_payload=dict(BUY),
        job_user_id=w.user_id,
        job_broker_account_id=w.broker_account_id,
        job_idempotency_key="k",
        account_environment="demo",
        settings=SETTINGS,
        account_snapshot=_snap(),
        now=NOW,
        user_caps=CAPS,
    )
    assert auth.order_send_allowed is False
    assert "SUBSCRIPTION_INACTIVE" in auth.reasons
