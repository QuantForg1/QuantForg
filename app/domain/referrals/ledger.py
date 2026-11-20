"""Referral attribution. Rewards are not issued by this module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

QUALIFYING_EVENTS = frozenset({"paid_invoice"})


@dataclass(frozen=True, slots=True)
class Attribution:
    referred_user_id: str
    referrer_user_id: str
    code: str


def normalize_code(raw: str) -> str | None:
    text = raw.strip().upper()
    if not text or len(text) > 32:
        return None
    if any(not (character.isalnum() or character == "-") for character in text):
        return None
    return text


def attribute_referral(
    *,
    code: str,
    referrer_user_id: str,
    referred_user_id: str,
    existing: tuple[Attribution, ...] = (),
) -> dict[str, Any]:
    """Accept one attribution. Self-referral and a second claim are rejected."""
    normalized = normalize_code(code)
    referrer = referrer_user_id.strip()
    referred = referred_user_id.strip()
    if normalized is None or not referrer or not referred:
        return _rejected("invalid_referral")
    if referrer == referred:
        return _rejected("self_referral")
    if any(item.referred_user_id == referred for item in existing):
        return _rejected("duplicate_attribution")
    return {
        "status": "attributed",
        "reason": "registration_attributed",
        "code": normalized,
        "referrer_user_id": referrer,
        "referred_user_id": referred,
        "reward_amount": None,
        "reward_status": "not_qualified",
    }


def record_qualifying_event(
    *,
    event_id: str,
    event_type: str,
    already_recorded: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Record a real event. No reward amount is created here."""
    identity = event_id.strip()
    kind = event_type.strip()
    if not identity or not kind:
        return {
            "status": "rejected",
            "reason": "invalid_event",
            "reward_amount": None,
            "reward_status": "not_issued",
        }
    if identity in already_recorded:
        return {
            "status": "rejected",
            "reason": "duplicate_event",
            "reward_amount": None,
            "reward_status": "not_issued",
        }
    if kind not in QUALIFYING_EVENTS:
        return {
            "status": "recorded",
            "reason": "event_not_qualifying",
            "reward_amount": None,
            "reward_status": "not_qualified",
        }
    return {
        "status": "eligible",
        "reason": "qualifying_event_recorded_reward_not_issued",
        "event_id": identity,
        "event_type": kind,
        "reward_amount": None,
        "reward_status": "not_issued",
    }


def _rejected(reason: str) -> dict[str, Any]:
    return {
        "status": "rejected",
        "reason": reason,
        "reward_amount": None,
        "reward_status": "not_issued",
    }
