"""Referral attribution rejects self-deals and does not invent rewards."""

from __future__ import annotations

import pytest

from app.domain.referrals.ledger import (
    Attribution,
    attribute_referral,
    record_qualifying_event,
)

pytestmark = pytest.mark.unit


def test_self_referral_and_duplicate_are_rejected() -> None:
    first = attribute_referral(
        code="gold-1",
        referrer_user_id="user-a",
        referred_user_id="user-b",
    )
    assert first["status"] == "attributed"
    assert first["reward_amount"] is None
    own = attribute_referral(
        code="gold-1",
        referrer_user_id="user-a",
        referred_user_id="user-a",
    )
    assert own["reason"] == "self_referral"
    again = attribute_referral(
        code="gold-1",
        referrer_user_id="user-c",
        referred_user_id="user-b",
        existing=(
            Attribution(
                referred_user_id="user-b",
                referrer_user_id="user-a",
                code="GOLD-1",
            ),
        ),
    )
    assert again["reason"] == "duplicate_attribution"


def test_qualifying_event_does_not_create_a_payout() -> None:
    paid = record_qualifying_event(event_id="invoice-1", event_type="paid_invoice")
    assert paid["status"] == "eligible"
    assert paid["reward_amount"] is None
    assert paid["reward_status"] == "not_issued"
    replay = record_qualifying_event(
        event_id="invoice-1",
        event_type="paid_invoice",
        already_recorded=frozenset({"invoice-1"}),
    )
    assert replay["reason"] == "duplicate_event"
    visit = record_qualifying_event(event_id="visit-1", event_type="page_view")
    assert visit["reward_status"] == "not_qualified"
