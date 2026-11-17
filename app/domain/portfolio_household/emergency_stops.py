"""Auditable user / account / broker emergency stops (new orders only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EmergencyStopEvent:
    scope: str  # user | account | broker
    scope_id: str
    armed: bool
    reason: str
    actor_user_id: str | None
    at: datetime


@dataclass
class EmergencyStopStore:
    """In-process store with audit trail (durable write best-effort by caller)."""

    _user: set[str] = field(default_factory=set)
    _account: set[str] = field(default_factory=set)
    _broker: set[str] = field(default_factory=set)
    _audit: list[EmergencyStopEvent] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def arm(
        self,
        *,
        scope: str,
        scope_id: str | UUID,
        reason: str,
        actor_user_id: UUID | None = None,
    ) -> EmergencyStopEvent:
        sid = str(scope_id)
        with self._lock:
            bucket = self._bucket(scope)
            bucket.add(sid)
            ev = EmergencyStopEvent(
                scope=scope,
                scope_id=sid,
                armed=True,
                reason=reason or "armed",
                actor_user_id=str(actor_user_id) if actor_user_id else None,
                at=datetime.now(UTC),
            )
            self._audit.append(ev)
            return ev

    def disarm(
        self,
        *,
        scope: str,
        scope_id: str | UUID,
        reason: str,
        actor_user_id: UUID | None = None,
    ) -> EmergencyStopEvent:
        sid = str(scope_id)
        with self._lock:
            bucket = self._bucket(scope)
            bucket.discard(sid)
            ev = EmergencyStopEvent(
                scope=scope,
                scope_id=sid,
                armed=False,
                reason=reason or "disarmed",
                actor_user_id=str(actor_user_id) if actor_user_id else None,
                at=datetime.now(UTC),
            )
            self._audit.append(ev)
            return ev

    def is_armed(
        self,
        *,
        user_id: UUID | None = None,
        broker_account_id: UUID | str | None = None,
        broker_code: str | None = None,
    ) -> str | None:
        """Return block reason if any matching stop is armed."""
        with self._lock:
            if user_id is not None and str(user_id) in self._user:
                return "HOUSEHOLD_STOP: user emergency stop armed — new entries blocked"
            if (
                broker_account_id is not None
                and str(broker_account_id) in self._account
            ):
                return (
                    "HOUSEHOLD_STOP: account emergency stop armed — new entries blocked"
                )
            if broker_code is not None and broker_code.lower() in {
                b.lower() for b in self._broker
            }:
                return (
                    "HOUSEHOLD_STOP: broker emergency stop armed — new entries blocked"
                )
        return None

    def armed_by(self, *, scope: str, scope_id: str | UUID) -> str | None:
        """Actor of the arming event for a currently armed stop (None if not armed)."""
        sid = str(scope_id)
        with self._lock:
            if sid not in self._bucket(scope):
                return None
            for ev in reversed(self._audit):
                if ev.scope == scope and ev.scope_id == sid and ev.armed:
                    return ev.actor_user_id or ""
        return ""

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "users": sorted(self._user),
                "accounts": sorted(self._account),
                "brokers": sorted(self._broker),
                "audit_tail": [
                    {
                        "scope": e.scope,
                        "scope_id": e.scope_id,
                        "armed": e.armed,
                        "reason": e.reason,
                        "actor_user_id": e.actor_user_id,
                        "at": e.at.isoformat(),
                    }
                    for e in self._audit[-50:]
                ],
            }

    def _bucket(self, scope: str) -> set[str]:
        if scope == "user":
            return self._user
        if scope == "account":
            return self._account
        if scope == "broker":
            return self._broker
        raise ValueError(f"unknown emergency stop scope: {scope}")


_STORE = EmergencyStopStore()


def get_emergency_stop_store() -> EmergencyStopStore:
    return _STORE
