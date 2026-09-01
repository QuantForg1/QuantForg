"""OMS uses the live catalogue gold name, not uppercased XAUUSD_I."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.institutional_execution_engine import (
    mask_account_login,
    order_attempt_execution_result,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter


@pytest.mark.unit
@pytest.mark.trading_core
def test_oms_constraints_resolve_xauusd_i_to_mock_catalogue_xauusd() -> None:
    adapter = MT5Adapter(client=MockMT5Client())
    adapter.initialize()
    adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
    service = MT5OrderValidationService(adapter=adapter)

    constraints = service.constraints_for("XAUUSD_I")

    assert constraints.symbol == "XAUUSD"
    assert constraints.min_volume == Decimal("0.01")


@pytest.mark.unit
def test_mask_account_login_never_emits_full_login() -> None:
    assert mask_account_login(12345678) == "12***78"
    assert mask_account_login(None) is None
    masked = mask_account_login(42)
    assert masked is not None
    assert "42" not in masked or masked == "***"


@pytest.mark.unit
@pytest.mark.trading_core
def test_order_attempt_never_calls_failed_send_a_fill() -> None:
    failed = order_attempt_execution_result(
        order_send_reached=False,
        ticket=None,
        outcome="rejected",
        retcode=None,
        message="symbol_info unavailable for XAUUSD_I",
    )
    assert "FILLED" not in failed
    assert "NO BROKER ORDER WAS SUBMITTED" in failed

    sent_fail = order_attempt_execution_result(
        order_send_reached=True,
        ticket=None,
        outcome="failed",
        retcode=10016,
        message="Invalid stops",
    )
    assert "FILLED" not in sent_fail
    assert "ORDER_SEND_FAILED" in sent_fail

    filled = order_attempt_execution_result(
        order_send_reached=True,
        ticket=91001122,
        outcome="success",
        retcode=10009,
        message="done",
    )
    assert filled == "FILLED ticket=91001122"

    fake_success = order_attempt_execution_result(
        order_send_reached=True,
        ticket=None,
        outcome="success",
        retcode=10009,
        message="done",
    )
    assert "FILLED" not in fake_success
