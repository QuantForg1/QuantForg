"""Support Operations Center — tickets, notes, timeline, audit."""

from __future__ import annotations

import re
from typing import Any

from app.domain.customer_operations.cop_audit import record_cop_audit
from app.domain.customer_operations.cop_persistence import (
    JsonDocumentStore,
    PostgresDocumentStore,
    durable_document_store,
    new_id,
    redact,
    utc_iso,
)

TICKET_STATUSES = frozenset(
    {
        "open",
        "in_progress",
        "waiting_customer",
        "escalated",
        "resolved",
        "closed",
        # legacy aliases retained for stored rows
        "pending",
        "assigned",
    }
)

OPEN_TICKET_STATUSES = frozenset(
    {"open", "pending", "in_progress", "waiting_customer", "escalated"}
)

SUPPORT_CATEGORIES = frozenset(
    {"general", "billing", "broker", "mt5", "technical", "account", "feedback"}
)

PLATFORM_HELP_FAQ: tuple[tuple[str, str], ...] = (
    (
        "How does QuantForg work?",
        "Create an account, connect your own broker, and grant only the permissions "
        "you choose. Market data and signals inform analysis; live orders are sent "
        "only after existing risk checks pass. A signal is not an order.",
    ),
    (
        "Is my account safe?",
        "Capital stays at your broker. QuantForg does not expose broker passwords "
        "after entry. Orders must pass the risk engine and broker permissions.",
    ),
    (
        "What symbols can I trade?",
        "The live desk focuses on XAUUSD. Other symbols are not marketed as a "
        "public trading universe; connected sessions show instruments the gateway "
        "returns from your broker.",
    ),
    (
        "Which brokers are supported?",
        "QuantForg connects MetaTrader 5 accounts. The Broker page lists the "
        "brokers you can choose: Weltrade, XM, Exness, HFM, IC Markets, "
        "Pepperstone, FP Markets and JustMarkets. You connect only an account "
        "you own, and each account can belong to one QuantForg user only.",
    ),
    (
        "What happens after I connect a broker?",
        "The gateway loads account status, quotes, and positions. Execution still "
        "waits for risk validation; failed checks block the order.",
    ),
    (
        "How do I get help from a human?",
        "Open a support ticket from the Support desk or widget and use Request human "
        "agent. A human is shown as connected only after staff accepts the escalation.",
    ),
    (
        "Where is platform status?",
        "The system status card on this Support page shows whether QuantForg is "
        "up. If something looks wrong with your account, open a ticket.",
    ),
    (
        "Why does my broker account say queued?",
        "Your account is saved securely and is waiting for its own dedicated "
        "trading terminal. Until a terminal is assigned and has verified your "
        "login, the robot does not trade on your account. You do not need to "
        "connect again.",
    ),
    (
        "The Broker page says it can't check my connection. What should I do?",
        "That means the trading terminal did not answer in time. It does not "
        "mean your account was disconnected. Press Retry after a minute. If it "
        "continues for more than 15 minutes, open a support ticket.",
    ),
    (
        "Does the robot trade Forex pairs?",
        "No. The robot trades gold (XAUUSD) only. Your broker's gold symbol is "
        "checked from the broker's own contract details before any order.",
    ),
    (
        "Should I start with a demo account?",
        "Yes. Connect a demo account first, watch how the robot behaves, and "
        "only then consider a live account. Trading involves risk of loss.",
    ),
)

# Help Center guides. Customer-facing: plain language, no owner-only policy
# values, nothing that promises trading before it is verified.
HELP_GUIDES: tuple[dict[str, Any], ...] = (
    {
        "id": "get-started",
        "title": "Create your account",
        "summary": "Sign up, confirm your email and sign in.",
        "steps": (
            "Open quantforg.com and choose Sign up.",
            "Enter your email and a strong password you do not use anywhere else.",
            "Open the confirmation email and follow the link.",
            "Sign in. You land on your dashboard.",
        ),
    },
    {
        "id": "demo-account",
        "title": "Get a demo account from your broker",
        "summary": "Practise with virtual money before using a live account.",
        "steps": (
            "On your broker's website, open a MetaTrader 5 demo account.",
            "Write down the login number, the password and the exact server name "
            "the broker gives you.",
            "Keep the password private. QuantForg staff will never ask for it.",
        ),
    },
    {
        "id": "connect-broker",
        "title": "Connect your broker account",
        "summary": "Link the MetaTrader 5 account you own.",
        "steps": (
            "Go to Broker Accounts.",
            "Choose your broker, then pick the exact server from the list.",
            "Enter your MT5 login and the trading (master) password.",
            "Press Connect. The password is stored encrypted and is never shown "
            "again.",
            "Your account appears as queued until its own trading terminal has "
            "verified the login. Only then can the robot use it.",
        ),
        "notes": (
            "An investor (read-only) password cannot place trades.",
            "One MT5 account can belong to one QuantForg user only.",
        ),
    },
    {
        "id": "manage-connection",
        "title": "Reconnect, disconnect or change account",
        "summary": "Keep your connection healthy and switch accounts safely.",
        "steps": (
            "Reconnect: use it if the page shows the account as disconnected. "
            "It reuses your saved login.",
            "Disconnect: stops the robot from using the account. Your trade "
            "history stays. Open positions are not closed for you; manage them "
            "in MetaTrader.",
            "Change account: enter the new login. Your current account stays "
            "connected until the new one is verified.",
        ),
    },
    {
        "id": "gold-robot",
        "title": "Set up the gold robot",
        "summary": "How the robot trades and what you control.",
        "steps": (
            "The robot trades gold (XAUUSD) only, during main market hours on "
            "weekdays.",
            "Open Robot Control Center to see whether the robot is enabled for "
            "your account and why it is or is not trading.",
            "Use Pause to stop new trades at any time. Pause does not close "
            "open positions.",
        ),
    },
    {
        "id": "risk",
        "title": "How risk is controlled",
        "summary": "Limits that protect your account.",
        "steps": (
            "Every order passes platform risk checks: position size, daily loss "
            "limit, spread, signal quality and trading hours.",
            "You can set your own limits in Risk Center. Your settings can make "
            "trading stricter, never looser, than the platform limits.",
            "If a check fails, no order is sent. The reason appears in Robot "
            "Control Center.",
            "Trading involves risk. Losses can happen even when every check passes.",
        ),
    },
    {
        "id": "troubleshooting",
        "title": "Troubleshooting",
        "summary": "Common problems and what to do.",
        "steps": (
            "Wrong password or server: reconnect with the exact server name from "
            "your broker.",
            "Account queued for a long time: open a ticket; we will check the "
            "terminal assignment.",
            "Can't check connection: wait a minute and press Retry; your account "
            "is not disconnected.",
            "Robot not trading: check Robot Control Center for the reason "
            "(outside trading hours, spread too wide, paused, or no valid signal).",
        ),
    },
    {
        "id": "support",
        "title": "Get help",
        "summary": "How to reach the support team.",
        "steps": (
            "Ask the help assistant on this page for quick answers.",
            "Open a ticket for anything about your account. Include what you "
            "saw and when.",
            "Choose Request human agent to talk to a person. We will never ask "
            "for your password.",
        ),
    },
)

_ACTION_REFUSAL = re.compile(
    r"\b("
    r"execute|place\s+(?:an?\s+)?(?:\w+\s+)?(?:order|trade)|"
    r"(?:buy|sell)\s+(?:order|now)|open\s+(?:a\s+)?(?:\w+\s+)?position|"
    r"close\s+(?:my\s+|the\s+|a\s+)?(?:\w+\s+)?positions?|"
    r"change\s+risk|override\s+risk|disable\s+risk|force\s+trade|"
    r"enable\s+live|turn\s+on\s+auto|modify\s+settings|reset\s+password"
    r")\b",
    re.I,
)

_TICKETS: JsonDocumentStore | PostgresDocumentStore | None = None


def get_support_ticket_store() -> JsonDocumentStore | PostgresDocumentStore:
    global _TICKETS
    if _TICKETS is None:
        _TICKETS = durable_document_store("cop_support_tickets.json", "tickets")
    return _TICKETS


def _normalize_status(status: str | None, *, default: str = "open") -> str:
    raw = str(status or default).strip().lower()
    if raw in TICKET_STATUSES:
        return raw
    return default


def _ticket_user_id(ticket: dict[str, Any]) -> str | None:
    uid = ticket.get("user_id") or ticket.get("customer_id")
    return str(uid) if uid else None


def ticket_owned_by(ticket: dict[str, Any], user_id: str) -> bool:
    owner = _ticket_user_id(ticket)
    if not owner:
        return False
    return owner == str(user_id)


def _ensure_messages(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    messages = ticket.get("messages")
    if isinstance(messages, list) and messages:
        return messages
    body = str(ticket.get("body") or "").strip()
    if not body:
        return []
    return [
        {
            "id": new_id("msg"),
            "at": ticket.get("created_at") or utc_iso(),
            "role": "customer",
            "author": _ticket_user_id(ticket) or "customer",
            "body": body,
        }
    ]


def customer_ticket_view(ticket: dict[str, Any]) -> dict[str, Any]:
    """Strip operator-only fields for client support desk."""
    redacted = redact(dict(ticket))
    out: dict[str, Any] = redacted if isinstance(redacted, dict) else dict(ticket)
    out["messages"] = [
        m
        for m in _ensure_messages(ticket)
        if isinstance(m, dict) and str(m.get("role")) != "internal"
    ]
    out.pop("internal_notes", None)
    out.pop("audit_log", None)
    out["human_agent_connected"] = bool(
        out.get("human_accepted") and str(out.get("status")) in OPEN_TICKET_STATUSES
    )
    return out


def list_tickets_for_user(user_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    uid = str(user_id)
    rows = [
        customer_ticket_view(t)
        for t in get_support_ticket_store().list(limit=500)
        if ticket_owned_by(t, uid)
    ]
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows[:limit]


def get_ticket_for_user(ticket_id: str, user_id: str) -> dict[str, Any] | None:
    ticket = get_support_ticket_store().get(ticket_id)
    if ticket is None or not ticket_owned_by(ticket, user_id):
        return None
    return customer_ticket_view(ticket)


def build_support_center() -> dict[str, Any]:
    tickets = list(reversed(get_support_ticket_store().list(limit=500)))
    pending = [
        t for t in tickets if _normalize_status(t.get("status")) in OPEN_TICKET_STATUSES
    ]
    return {
        "as_of": utc_iso(),
        "tickets": tickets,
        "pending_requests": pending,
        "count": len(tickets),
        "pending_count": len(pending),
        "fabricated": False,
        "observe_only_reads": False,
        "modifies_trading": False,
    }


def create_support_ticket(
    *,
    subject: str,
    customer_id: str | None,
    priority: str = "normal",
    operator: str,
    ip: str | None = None,
    body: str = "",
    user_id: str | None = None,
    category: str | None = None,
    ai_session_id: str | None = None,
) -> dict[str, Any]:
    now = utc_iso()
    body_text = str(body or "").strip()
    cat = str(category or "general").lower()
    if cat not in SUPPORT_CATEGORIES:
        cat = "general"
    uid = user_id or customer_id
    messages: list[dict[str, Any]] = []
    if body_text:
        messages.append(
            {
                "id": new_id("msg"),
                "at": now,
                "role": "customer",
                "author": str(operator),
                "body": body_text,
            }
        )
    ticket = {
        "id": new_id("sup"),
        "created_at": now,
        "updated_at": now,
        "subject": str(subject or "").strip() or "Support request",
        "customer_id": customer_id or uid,
        "user_id": uid,
        "category": cat,
        "priority": str(priority or "normal").lower(),
        "status": "open",
        "assigned_staff": None,
        "human_requested": False,
        "human_accepted": False,
        "ai_session_id": ai_session_id,
        "messages": messages,
        "internal_notes": [],
        "resolution_timeline": [
            {
                "at": now,
                "event": "created",
                "by": operator,
            }
        ],
        "attachments": [],
        "audit_log": [],
        "body": body_text,
    }
    saved = get_support_ticket_store().append(ticket)
    record_cop_audit(
        operator=operator,
        action="support_ticket_create",
        target=saved["id"],
        before=None,
        after={"id": saved["id"], "subject": saved["subject"]},
        ip=ip,
    )
    redacted: dict[str, Any] = redact(saved)
    return redacted


def append_ticket_message(
    *,
    ticket_id: str,
    body: str,
    role: str,
    author: str,
    operator: str,
    ip: str | None = None,
    customer_user_id: str | None = None,
) -> dict[str, Any] | None:
    text = str(body or "").strip()
    if not text:
        return None
    before = get_support_ticket_store().get(ticket_id)
    if before is None:
        return None
    if customer_user_id is not None and not ticket_owned_by(before, customer_user_id):
        return None

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        row.setdefault("messages", _ensure_messages(row))
        row["messages"].append(
            {
                "id": new_id("msg"),
                "at": utc_iso(),
                "role": str(role),
                "author": str(author),
                "body": text,
            }
        )
        row["body"] = text
        if role == "customer" and _normalize_status(row.get("status")) not in {
            "resolved",
            "closed",
        }:
            row["status"] = "open"
        elif role == "staff":
            row["status"] = "waiting_customer"
            if row.get("human_requested") and row.get("human_accepted"):
                row["status"] = "in_progress"
        row.setdefault("resolution_timeline", []).append(
            {"at": utc_iso(), "event": f"message:{role}", "by": operator}
        )
        return row

    updated = get_support_ticket_store().upsert(ticket_id, mutator)
    if updated:
        record_cop_audit(
            operator=operator,
            action="support_ticket_message",
            target=ticket_id,
            before=None,
            after={"role": role, "len": len(text)},
            ip=ip,
        )
    return updated


def request_human_on_ticket(
    *,
    ticket_id: str,
    user_id: str,
    operator: str,
    ip: str | None = None,
) -> dict[str, Any] | None:
    before = get_support_ticket_store().get(ticket_id)
    if before is None or not ticket_owned_by(before, user_id):
        return None

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        row["human_requested"] = True
        row["status"] = "escalated"
        row.setdefault("resolution_timeline", []).append(
            {"at": utc_iso(), "event": "human_requested", "by": operator}
        )
        return row

    updated = get_support_ticket_store().upsert(ticket_id, mutator)
    if updated:
        record_cop_audit(
            operator=operator,
            action="support_human_requested",
            target=ticket_id,
            before={"human_requested": before.get("human_requested")},
            after={"human_requested": True, "status": "escalated"},
            ip=ip,
        )
    return customer_ticket_view(updated) if updated else None


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def answer_support_faq(
    *,
    message: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """FAQ-only assistant — never acts on trading or settings."""
    question = str(message or "").strip()
    sid = session_id or new_id("ais")
    if _ACTION_REFUSAL.search(question):
        return {
            "ai_session_id": sid,
            "answer": (
                "I can only answer platform help questions. I cannot execute trades, "
                "change risk settings, or modify your account. Open a support ticket "
                "or request a human agent for account-specific help."
            ),
            "confidence": "refused",
            "suggest_ticket": True,
            "suggest_human": True,
            "sources": [],
            "executes_actions": False,
        }

    q_tokens = _tokenize(question)
    best_score = 0
    best: tuple[str, str] | None = None
    for title, body in PLATFORM_HELP_FAQ:
        score = len(q_tokens & _tokenize(f"{title} {body}"))
        if score > best_score:
            best_score = score
            best = (title, body)

    if best and best_score >= 2:
        return {
            "ai_session_id": sid,
            "answer": f"{best[1]}",
            "confidence": "matched",
            "suggest_ticket": False,
            "suggest_human": False,
            "sources": [{"title": best[0]}],
            "executes_actions": False,
        }

    return {
        "ai_session_id": sid,
        "answer": (
            "I am not certain about that from our verified help articles. "
            "Please open a support ticket with details, or request a human agent "
            "if this is urgent."
        ),
        "confidence": "low",
        "suggest_ticket": True,
        "suggest_human": True,
        "sources": [],
        "executes_actions": False,
    }


def update_support_ticket(
    *,
    ticket_id: str,
    operator: str,
    ip: str | None = None,
    status: str | None = None,
    assigned_staff: str | None = None,
    priority: str | None = None,
    internal_note: str | None = None,
    attachment_name: str | None = None,
    public_message: str | None = None,
    human_accepted: bool | None = None,
) -> dict[str, Any] | None:
    before = get_support_ticket_store().get(ticket_id)
    if before is None:
        return None

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        if status:
            default_status = str(row.get("status") or "open")
            row["status"] = _normalize_status(status, default=default_status)
            row.setdefault("resolution_timeline", []).append(
                {
                    "at": utc_iso(),
                    "event": f"status:{row['status']}",
                    "by": operator,
                }
            )
        if human_accepted is not None:
            row["human_accepted"] = bool(human_accepted)
            row.setdefault("resolution_timeline", []).append(
                {
                    "at": utc_iso(),
                    "event": f"human_accepted:{human_accepted}",
                    "by": operator,
                }
            )
        if public_message:
            row.setdefault("messages", _ensure_messages(row))
            row["messages"].append(
                {
                    "id": new_id("msg"),
                    "at": utc_iso(),
                    "role": "staff",
                    "author": operator,
                    "body": str(public_message).strip(),
                }
            )
        if assigned_staff is not None:
            row["assigned_staff"] = assigned_staff
            row.setdefault("resolution_timeline", []).append(
                {
                    "at": utc_iso(),
                    "event": f"assigned:{assigned_staff}",
                    "by": operator,
                }
            )
        if priority:
            row["priority"] = str(priority).lower()
        if internal_note:
            row.setdefault("internal_notes", []).append(
                {"at": utc_iso(), "by": operator, "note": internal_note}
            )
        if attachment_name:
            # Metadata only — no binary storage of secrets
            row.setdefault("attachments", []).append(
                {
                    "at": utc_iso(),
                    "name": str(attachment_name)[:200],
                    "by": operator,
                }
            )
        row.setdefault("audit_log", []).append(
            {
                "at": utc_iso(),
                "by": operator,
                "action": "update",
            }
        )
        return row

    updated = get_support_ticket_store().upsert(ticket_id, mutator)
    record_cop_audit(
        operator=operator,
        action="support_ticket_update",
        target=ticket_id,
        before={
            "status": before.get("status"),
            "assigned": before.get("assigned_staff"),
        },
        after={
            "status": (updated or {}).get("status"),
            "assigned": (updated or {}).get("assigned_staff"),
        },
        ip=ip,
    )
    return updated
