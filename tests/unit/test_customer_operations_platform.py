"""Customer Operations Platform — additive ops; never touches trading."""

from __future__ import annotations

import pytest

from app.domain.customer_operations.cop_audit import list_cop_audit, record_cop_audit
from app.domain.customer_operations.cop_persistence import redact
from app.domain.customer_operations.notifications_center import (
    CHANNELS,
    build_notifications_center,
    publish_notification,
)
from app.domain.customer_operations.support_center import (
    answer_support_faq,
    build_support_center,
    create_support_ticket,
    get_ticket_for_user,
    list_tickets_for_user,
    ticket_owned_by,
    update_support_ticket,
)


def test_redact_strips_secrets() -> None:
    raw = {
        "login": "12345",
        "password": "secret",
        "nested": {"api_key": "x", "ok": 1},
    }
    out = redact(raw)
    assert out["password"] == "[REDACTED]"
    assert out["nested"]["api_key"] == "[REDACTED]"
    assert out["nested"]["ok"] == 1
    assert out["login"] == "12345"


def test_cop_audit_immutable_fields() -> None:
    row = record_cop_audit(
        operator="ops@quantforg.com",
        action="test_action",
        target="cust_1",
        before={"status": "a"},
        after={"status": "b"},
        ip="127.0.0.1",
    )
    assert row["immutable"] is True
    assert row["append_only"] is True
    assert row["trading_impact"] is False
    assert row["modifies_ai"] is False
    assert row["fingerprint"]
    listed = list_cop_audit(limit=10)
    assert listed["immutable"] is True
    assert listed["count"] >= 1


def test_support_ticket_lifecycle() -> None:
    ticket = create_support_ticket(
        subject="Connectivity",
        customer_id="user-1",
        priority="high",
        operator="admin@quantforg.com",
        ip="10.0.0.1",
    )
    assert ticket["status"] == "open"
    assert ticket.get("user_id") == "user-1"
    assert ticket["priority"] == "high"
    updated = update_support_ticket(
        ticket_id=ticket["id"],
        operator="admin@quantforg.com",
        status="in_progress",
        assigned_staff="desk-1",
        internal_note="Investigating gateway",
        attachment_name="screenshot.png",
    )
    assert updated is not None
    assert updated["status"] == "in_progress"
    assert updated["assigned_staff"] == "desk-1"
    assert len(updated["internal_notes"]) >= 1
    assert len(updated["attachments"]) >= 1
    center = build_support_center()
    assert center["count"] >= 1


def test_support_ticket_ownership_and_customer_view() -> None:
    alice = create_support_ticket(
        subject="Billing",
        customer_id="alice-id",
        user_id="alice-id",
        operator="alice@example.com",
        body="Invoice question",
    )
    bob = create_support_ticket(
        subject="MT5",
        customer_id="bob-id",
        user_id="bob-id",
        operator="bob@example.com",
        body="Gateway",
    )
    assert ticket_owned_by(alice, "alice-id")
    assert not ticket_owned_by(alice, "bob-id")
    alice_list = list_tickets_for_user("alice-id")
    assert any(t["id"] == alice["id"] for t in alice_list)
    assert all(t["id"] != bob["id"] for t in alice_list)
    assert get_ticket_for_user(alice["id"], "alice-id") is not None
    assert get_ticket_for_user(bob["id"], "alice-id") is None
    view = get_ticket_for_user(alice["id"], "alice-id")
    assert view is not None
    assert "internal_notes" not in view


def test_support_ai_refuses_trading_actions() -> None:
    out = answer_support_faq(message="Please place a buy order on XAUUSD now")
    assert out["executes_actions"] is False
    assert out["suggest_ticket"] is True


def test_notifications_channels() -> None:
    assert "customer" in CHANNELS
    assert "security" in CHANNELS
    publish_notification(
        channel="operator",
        title="COP online",
        message="Customer Operations Platform ready",
        operator="admin@quantforg.com",
    )
    center = build_notifications_center(channel="operator")
    assert center["count"] >= 1
    assert center["fabricated"] is False


@pytest.mark.asyncio
async def test_platform_flags_never_modify_trading() -> None:
    from app.application.services.customer_operations_platform import (
        build_customer_operations_platform,
    )

    pack = await build_customer_operations_platform()
    flags = pack["flags"]
    assert flags["modifies_trading"] is False
    assert flags["modifies_ai"] is False
    assert flags["modifies_oms"] is False
    assert flags["modifies_mt5"] is False
    assert flags["modifies_risk"] is False
    assert flags["modifies_pricing"] is False
    assert flags["modifies_licensing_rules"] is False
    assert flags["credentials_exposed"] is False
    assert flags["additive_only"] is True
    assert pack["fabricated"] is False


@pytest.mark.asyncio
async def test_noc_panels_observe_only() -> None:
    from app.application.services.customer_operations_platform import (
        build_customer_ops_noc_panels,
    )

    panels = await build_customer_ops_noc_panels()
    assert "customer_fleet" in panels
    assert "license_health" in panels
    assert "broker_fleet" in panels
    assert "support" in panels
    assert "enterprise_analytics" in panels
    assert panels["flags"]["never_modifies_trading"] is True
    assert panels["broker_fleet"]["credentials_exposed"] is False
