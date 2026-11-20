"""Referral program — no self-referral, no invented payout."""

from __future__ import annotations

import pytest

from app.application.services.referral_program import (
    MemoryReferralStore,
    ReferralProgram,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_attribution_is_isolated_and_unpaid() -> None:
    program = ReferralProgram(MemoryReferralStore())
    owner = await program.summary("user-a")
    other = await program.summary("user-b")
    assert owner["code"] != other["code"]
    assert owner["reward_balance"] is None
    saved = await program.attribute(user_id="user-b", code=owner["code"])
    assert saved["status"] == "attributed"
    assert saved["reward_amount"] is None
    own = await program.attribute(user_id="user-a", code=owner["code"])
    assert own["reason"] == "self_referral"
    third = await program.summary("user-c")
    again = await program.attribute(user_id="user-b", code=third["code"])
    assert again["reason"] == "duplicate_attribution"
    history = await program.summary("user-a")
    assert len(history["history"]) == 1
    assert "user-b" not in str(history["history"])
    stranger = await program.summary("user-d")
    assert stranger["history"] == []


@pytest.mark.asyncio
async def test_qualifying_event_does_not_create_a_balance() -> None:
    program = ReferralProgram(MemoryReferralStore())
    owner = await program.summary("user-a")
    await program.attribute(user_id="user-b", code=owner["code"])
    event = await program.record_event(
        event_id="invoice-1",
        event_type="paid_invoice",
        referred_user_id="user-b",
    )
    assert event["reward_amount"] is None
    assert event["reward_status"] == "not_issued"
    replay = await program.record_event(
        event_id="invoice-1",
        event_type="paid_invoice",
        referred_user_id="user-b",
    )
    assert replay["reason"] == "duplicate_event"
    summary = await program.summary("user-a")
    assert summary["reward_balance"] is None
    assert summary["rewards"][0]["reward_amount"] is None


@pytest.mark.asyncio
async def test_paying_customer_cannot_be_attributed_after_the_fact() -> None:
    store = MemoryReferralStore()
    program = ReferralProgram(store)
    referrer = await program.summary("referrer")
    store.paid.add("customer")
    result = await program.attribute(user_id="customer", code=referrer["code"])
    assert result["status"] == "rejected"
    assert result["reason"] == "existing_customer"
    assert await store.attribution_for("customer") is None


@pytest.mark.asyncio
async def test_summary_reports_reward_days_and_register_link() -> None:
    store = MemoryReferralStore()
    store.rewards = [
        {"beneficiary_user_id": "r", "reward_status": "applied", "reward_days": 30},
        {"beneficiary_user_id": "r", "reward_status": "pending", "reward_days": 30},
        {"beneficiary_user_id": "other", "reward_status": "applied", "reward_days": 30},
    ]
    summary = await ReferralProgram(store).summary("r")
    assert summary["link_path"].startswith("/register?ref=")
    assert summary["reward_days_applied"] == 30
    assert summary["reward_days_pending"] == 30
    assert summary["reward_rule"]["days"] == 30
    assert summary["sales_or_payouts"] is False
