"""Operational status from supplied checks. A missing check is unknown."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "reliability-center.v1"
_STATES = frozenset(
    {"healthy", "degraded", "disconnected", "delayed", "unavailable", "unknown"}
)
_FRESH_SECONDS = 120


@dataclass(frozen=True, slots=True)
class ComponentCheck:
    name: str
    state: str | None = None
    checked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProtectionInput:
    read_at: datetime
    components: tuple[ComponentCheck, ...] = ()
    broker_account_verified: bool | None = None
    credentials_saved: bool | None = None
    session_connected: bool | None = None
    trading_authorized: bool | None = None
    subscription_active: bool | None = None
    robot_running: bool | None = None


def build_protection_report(spec: ProtectionInput) -> dict[str, Any]:
    """Report each supplied check. Saved credentials are not a live session."""
    observed = _aware(spec.read_at).isoformat()
    components = [_component(item, spec.read_at) for item in spec.components]
    return {
        "schema_version": SCHEMA_VERSION,
        "places_orders": False,
        "restarts_gateway": False,
        "authoritative_for_execution": False,
        "read_at": observed,
        "components": components,
        "account_states": {
            "broker_account_verified": _bool(spec.broker_account_verified),
            "credentials_saved": _bool(spec.credentials_saved),
            "session_connected": _bool(spec.session_connected),
            "trading_authorized": _bool(spec.trading_authorized),
            "subscription_active": _bool(spec.subscription_active),
            "robot_running": _bool(spec.robot_running),
        },
        "credentials_are_not_a_live_session": True,
    }


def _component(item: ComponentCheck, read_at: datetime) -> dict[str, Any]:
    state = (item.state or "").strip().lower()
    if state not in _STATES:
        state = "unknown"
    age = None
    if item.checked_at is not None:
        age = int((_aware(read_at) - _aware(item.checked_at)).total_seconds())
    if state == "healthy" and (age is None or age > _FRESH_SECONDS):
        state = "unknown"
        reason = "healthy_requires_a_check_within_120s"
    else:
        reason = "supplied_check"
    return {
        "name": item.name,
        "state": state,
        "checked_at": _checked_at(item),
        "age_seconds": age,
        "reason": reason,
    }


def _checked_at(item: ComponentCheck) -> str | None:
    if item.checked_at is None:
        return None
    return _aware(item.checked_at).isoformat()


def _bool(value: bool | None) -> dict[str, Any]:
    if value is None:
        return {"value": None, "status": "unknown"}
    return {"value": value, "status": "reported"}


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
