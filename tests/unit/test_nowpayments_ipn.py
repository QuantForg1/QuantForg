"""Unit tests for NOWPayments LIVE IPN signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.domain.billing.nowpayments import (
    NowPaymentsLiveClient,
    sort_object,
    verify_ipn_signature,
)
from app.domain.billing.plans import get_plan, plans_public


def _sign(payload: dict, secret: str) -> str:
    sorted_payload = sort_object(payload)
    encoded = json.dumps(sorted_payload, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(secret.encode(), encoded.encode(), hashlib.sha512).hexdigest()


@pytest.mark.unit
def test_plans_catalog() -> None:
    plans = plans_public()
    assert len(plans) == 3
    assert get_plan("premium") is not None
    assert get_plan("premium").license_tier == "enterprise"
    assert float(get_plan("starter").amount_usd) == 49.0


@pytest.mark.unit
def test_ipn_signature_valid() -> None:
    payload = {
        "payment_id": 12345,
        "payment_status": "finished",
        "price_amount": 99,
        "price_currency": "usd",
        "order_id": "qf_test_1",
        "pay_currency": "btc",
    }
    secret = "test-ipn-secret"
    sig = _sign(payload, secret)
    assert verify_ipn_signature(payload=payload, signature=sig, ipn_secret=secret)


@pytest.mark.unit
def test_ipn_signature_rejects_tamper() -> None:
    payload = {
        "payment_id": 1,
        "payment_status": "finished",
        "order_id": "qf_x",
        "price_amount": 49,
        "price_currency": "usd",
    }
    secret = "secret"
    sig = _sign(payload, secret)
    tampered = dict(payload)
    tampered["price_amount"] = 1
    assert not verify_ipn_signature(payload=tampered, signature=sig, ipn_secret=secret)


@pytest.mark.unit
def test_ipn_signature_rejects_wrong_secret() -> None:
    payload = {"payment_status": "waiting", "order_id": "a"}
    sig = _sign(payload, "a")
    assert not verify_ipn_signature(payload=payload, signature=sig, ipn_secret="b")


@pytest.mark.unit
def test_live_client_rejects_sandbox_host() -> None:
    with pytest.raises(ValueError, match="Sandbox"):
        NowPaymentsLiveClient(
            api_key="key",
            base_url="https://api-sandbox.nowpayments.io/v1",
        )


@pytest.mark.unit
def test_live_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="NOWPAYMENTS_API_KEY"):
        NowPaymentsLiveClient(api_key="")
