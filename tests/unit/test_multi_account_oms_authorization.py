"""OMS authorization preview — never order_send."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.multi_account_oms_authorization import (
    preview_oms_authorization,
)

pytestmark = [pytest.mark.unit]


def test_preview_authorized_when_ready() -> None:
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
    )
    preview = preview_oms_authorization(
        user_id=uuid4(),
        broker_account_id=uuid4(),
        symbol="XAUUSD",
        side="BUY",
        volume=Decimal("0.01"),
        stop_loss=Decimal("3990"),
        worker_dispatch_ready=True,
        ownership_verified=True,
        account_environment="demo",
        settings=settings,
    )
    assert preview.authorized is True
    assert preview.order_send is False
    assert preview.live_submit_flag is True
    assert preview.to_public_dict()["order_send"] is False
    assert "password" not in str(preview.to_public_dict()).lower()


def test_preview_fail_closed_without_sl_or_worker() -> None:
    settings = SimpleNamespace(
        multi_account_dispatch_enabled=True,
        multi_account_live_submit_enabled=True,
    )
    preview = preview_oms_authorization(
        user_id=uuid4(),
        broker_account_id=uuid4(),
        symbol="XAUUSD",
        side="BUY",
        volume="0.01",
        stop_loss=None,
        worker_dispatch_ready=False,
        ownership_verified=True,
        settings=settings,
    )
    assert preview.authorized is False
    assert "mandatory_stop_loss_missing" in preview.reasons
    assert "worker_not_dispatch_ready" in preview.reasons
