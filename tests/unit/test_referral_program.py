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
