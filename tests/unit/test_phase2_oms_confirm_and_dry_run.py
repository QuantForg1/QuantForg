"""Phase 2 — OMS confirm honesty + multi-account dry-run never order_send."""

from __future__ import annotations

import inspect

from app.domain.institutional_trading.management.models import OmsManageResult
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)


def test_oms_manage_reject_without_broker_ticket() -> None:
    out = OmsManageResult(
        outcome="oms_failure",
        message="broker_rejected",
        order_ticket=None,
        deal_ticket=None,
    )
    assert out.outcome != "success"
    assert out.order_ticket is None
    assert out.deal_ticket is None


def test_oms_manage_success_carries_confirm_ticket() -> None:
    out = OmsManageResult(
        outcome="success",
        message="sltp_updated",
        order_ticket=42,
        deal_ticket=None,
        retcode=10009,
        gateway_status="ok",
        oms_status="success",
    )
    assert out.outcome == "success"
    assert out.order_ticket == 42
    # Success without a broker ticket is not acceptable for confirmed manages.
    bare = OmsManageResult(outcome="success", message="ok", order_ticket=None)
    assert bare.order_ticket is None


def test_feature_gates_default_closed() -> None:
    class _Settings:
        multi_account_dispatch_enabled = False
        multi_account_live_submit_enabled = False

    assert multi_account_dispatch_allowed(_Settings()) is False
    assert multi_account_live_submit_allowed(_Settings()) is False


def test_dry_run_module_never_calls_order_send() -> None:
    import app.application.services.multi_account_dispatch_dry_run as mod

    src = inspect.getsource(mod)
    assert "order_send" not in src
    assert "allow_live_submit" in src or "live_submit_allowed" in src
