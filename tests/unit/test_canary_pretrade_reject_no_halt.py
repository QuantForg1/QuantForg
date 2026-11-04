"""Canary must not halt on owner-policy order_check_only rejects."""

from __future__ import annotations

from app.domain.institutional_trading.execution.bridge import _canary_reject_is_abnormal
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    OmsSubmitResult,
)


def test_owner_min_rr_order_check_only_is_not_abnormal() -> None:
    result = OmsSubmitResult(
        outcome="rejected",
        message="OWNER_MIN_RR: net reward:risk 0.07 < 0.20",
        retcode=None,
        gateway_status="order_check_only",
    )
    assert (
        _canary_reject_is_abnormal(result, BridgeAbortReason.OMS_FAILURE) is False
    )


def test_owner_sl_risk_order_check_only_is_not_abnormal() -> None:
    result = OmsSubmitResult(
        outcome="rejected",
        message=(
            "OWNER_SL_RISK: planned risk $4.56 > $4.23 (20% of equity 21.17). "
            "Tighten the stop."
        ),
        retcode=None,
        gateway_status="order_check_only",
    )
    assert (
        _canary_reject_is_abnormal(result, BridgeAbortReason.OMS_FAILURE) is False
    )


def test_mt5_rejection_retcode_is_abnormal() -> None:
    result = OmsSubmitResult(
        outcome="rejected",
        message="Request rejected",
        retcode=10006,
        gateway_status="order_send",
    )
    assert (
        _canary_reject_is_abnormal(result, BridgeAbortReason.MT5_REJECTION) is True
    )


def test_gateway_failure_is_abnormal() -> None:
    result = OmsSubmitResult(
        outcome="unavailable",
        message="gateway /orders timeout",
        retcode=10031,
        gateway_status="failed",
    )
    assert (
        _canary_reject_is_abnormal(result, BridgeAbortReason.GATEWAY_FAILURE) is True
    )
